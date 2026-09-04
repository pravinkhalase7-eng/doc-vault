"""Local-first classification, metadata extraction, chunking, and embeddings."""

from __future__ import annotations

import hashlib
import math
import re
from datetime import date, datetime
from pathlib import Path

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.documents.ocr import generate_reel_images, get_ocr_engine
from app.logging import get_logger
from app.models.document import Category, Document, DocumentChunk, DocumentMetadata, DocumentType
from app.models.enums import DocumentStatus, HIGHLY_SENSITIVE_TYPES, SensitivityLevel, VerificationStatus
from app.storage.local import resolve_key, thumbnail_path

log = get_logger("processing")
settings = get_settings()

KEYWORD_MAP = [
    ("aadhaar", "Aadhaar", "Government", SensitivityLevel.HIGHLY_SENSITIVE),
    ("uidai", "Aadhaar", "Government", SensitivityLevel.HIGHLY_SENSITIVE),
    ("permanent account", "PAN", "Government", SensitivityLevel.HIGHLY_SENSITIVE),
    ("income tax", "PAN", "Government", SensitivityLevel.HIGHLY_SENSITIVE),
    ("passport", "Passport", "Government", SensitivityLevel.HIGHLY_SENSITIVE),
    ("driving licence", "Driving Licence", "Government", SensitivityLevel.HIGHLY_SENSITIVE),
    ("driving license", "Driving Licence", "Government", SensitivityLevel.HIGHLY_SENSITIVE),
    ("voter", "Voter ID", "Government", SensitivityLevel.HIGHLY_SENSITIVE),
    ("registration certificate", "RC", "Vehicle", SensitivityLevel.SENSITIVE),
    ("puc", "PUC", "Vehicle", SensitivityLevel.PRIVATE),
    ("motor insurance", "Insurance", "Vehicle", SensitivityLevel.SENSITIVE),
    ("car insurance", "Insurance", "Vehicle", SensitivityLevel.SENSITIVE),
    ("policy", "Policy", "Insurance", SensitivityLevel.SENSITIVE),
    ("prescription", "Prescription", "Health", SensitivityLevel.HIGHLY_SENSITIVE),
    ("lab report", "Lab report", "Health", SensitivityLevel.HIGHLY_SENSITIVE),
    ("medical", "Medical report", "Health", SensitivityLevel.HIGHLY_SENSITIVE),
    ("marksheet", "Marksheet", "Education", SensitivityLevel.PRIVATE),
    ("degree", "Degree", "Education", SensitivityLevel.PRIVATE),
    ("education", "Education document", "Education", SensitivityLevel.PRIVATE),
    ("school", "School document", "Education", SensitivityLevel.PRIVATE),
    ("university", "Degree", "Education", SensitivityLevel.PRIVATE),
    ("college", "Certificate", "Education", SensitivityLevel.PRIVATE),
    ("invoice", "Invoice", "Finance", SensitivityLevel.SENSITIVE),
    ("receipt", "Receipt", "Finance", SensitivityLevel.SENSITIVE),
    ("bank statement", "Bank statement", "Finance", SensitivityLevel.HIGHLY_SENSITIVE),
    ("form 16", "Tax document", "Finance", SensitivityLevel.SENSITIVE),
]

EXPIRY_LABELS = re.compile(
    r"(valid till|valid until|expiry|expires on|exp(?:iry)?\.?\s*date)\s*[:\-]?\s*([0-9]{1,2}[-/][0-9]{1,2}[-/][0-9]{2,4}|[0-9]{4}[-/][0-9]{1,2}[-/][0-9]{1,2})",
    re.I,
)
ISSUE_LABELS = re.compile(
    r"(issue date|issued on|date of issue)\s*[:\-]?\s*([0-9]{1,2}[-/][0-9]{1,2}[-/][0-9]{2,4})",
    re.I,
)
POLICY_RE = re.compile(r"(policy(?:\s*no\.?| number)|policy #)\s*[:\-]?\s*([A-Z0-9\-\/]{6,})", re.I)
VEHICLE_RE = re.compile(r"\b([A-Z]{2}[0-9]{1,2}[A-Z]{1,3}[0-9]{4})\b")


def parse_date(value: str) -> date | None:
    value = value.replace(".", "/").strip()
    for fmt in ("%d/%m/%Y", "%d-%m-%Y", "%Y-%m-%d", "%d/%m/%y", "%d-%m-%y"):
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            continue
    return None


def classify_local(text: str, filename: str) -> tuple[str, str, SensitivityLevel, float]:
    hay = f"{filename}\n{text}".lower()
    for keyword, doc_type, category, sensitivity in KEYWORD_MAP:
        if keyword in hay:
            return doc_type, category, sensitivity, 0.82
    return "Other", "Other", SensitivityLevel.PRIVATE, 0.3


def extract_fields(text: str) -> list[dict]:
    fields: list[dict] = []
    expiry = EXPIRY_LABELS.search(text)
    if expiry:
        parsed = parse_date(expiry.group(2))
        if parsed:
            fields.append({"field_name": "expiry_date", "value": parsed.isoformat(), "confidence": 0.9, "page": 1})
    issue = ISSUE_LABELS.search(text)
    if issue:
        parsed = parse_date(issue.group(2))
        if parsed:
            fields.append({"field_name": "issue_date", "value": parsed.isoformat(), "confidence": 0.85, "page": 1})
    policy = POLICY_RE.search(text)
    if policy:
        fields.append({"field_name": "policy_number", "value": policy.group(2), "confidence": 0.8, "page": 1})
    vehicle = VEHICLE_RE.search(text.upper())
    if vehicle:
        fields.append({"field_name": "vehicle_number", "value": vehicle.group(1), "confidence": 0.8, "page": 1})
    return fields


def chunk_text(text: str, page_map: list[dict], size: int = 800, overlap: int = 120) -> list[dict]:
    chunks = []
    if not text.strip():
        return chunks
    start = 0
    index = 0
    while start < len(text):
        end = min(len(text), start + size)
        piece = text[start:end]
        page = 1
        for item in page_map:
            if item.get("text") and piece[:40] in item["text"]:
                page = item["page"]
                break
        chunks.append({"chunk_index": index, "text": piece, "page": page})
        index += 1
        start = end - overlap if end < len(text) else end
    return chunks


def local_embedding(text: str, dim: int) -> list[float]:
    digest = hashlib.sha256(text.encode("utf-8")).digest()
    values = []
    seed = digest
    while len(values) < dim:
        seed = hashlib.sha256(seed).digest()
        for b in seed:
            values.append(((b / 255.0) * 2) - 1)
            if len(values) == dim:
                break
    norm = math.sqrt(sum(v * v for v in values)) or 1.0
    return [v / norm for v in values]


async def process_document(db: AsyncSession, document_id: str) -> None:
    doc = await db.get(Document, document_id)
    if not doc or doc.deleted_at:
        return
    try:
        doc.status = DocumentStatus.PROCESSING
        await db.commit()
        path = resolve_key(doc.storage_key)
        engine = get_ocr_engine(settings.ocr_engine)
        doc.status = DocumentStatus.OCR_PROCESSING
        await db.commit()
        result = engine.extract(path, doc.mime_type)
        doc.ocr_text = result.get("text") or ""
        doc.page_count = result.get("page_count") or 1
        thumb, preview = await generate_reel_images(path, doc.user_id, doc.id, doc.mime_type)
        if thumb:
            doc.thumbnail_key = thumb
        if preview:
            doc.preview_key = preview

        doc.status = DocumentStatus.AI_PROCESSING
        await db.commit()

        doc_type, category_name, sensitivity, confidence = classify_local(doc.ocr_text, doc.original_filename)
        if doc.exclude_from_ai:
            sensitivity = doc.sensitivity
        else:
            doc.ai_classification = doc_type
            doc.ai_confidence = confidence
            doc.sensitivity = sensitivity
            cat = await db.scalar(select(Category).where(Category.name == category_name, Category.is_system.is_(True)))
            if cat:
                doc.category_id = cat.id
            dtype = await db.scalar(
                select(DocumentType).where(DocumentType.name == doc_type, DocumentType.is_system.is_(True))
            )
            if dtype:
                doc.document_type_id = dtype.id
                doc.sensitivity = dtype.default_sensitivity

        fields = extract_fields(doc.ocr_text or "")
        existing = (
            await db.scalars(select(DocumentMetadata).where(DocumentMetadata.document_id == doc.id))
        ).all()
        existing_names = {row.field_name for row in existing}
        for field in fields:
            if field["field_name"] in existing_names:
                continue
            db.add(
                DocumentMetadata(
                    user_id=doc.user_id,
                    document_id=doc.id,
                    field_name=field["field_name"],
                    value=field["value"],
                    confidence=field.get("confidence"),
                    page=field.get("page"),
                    source="local",
                    verification_status=VerificationStatus.UNVERIFIED,
                )
            )
            if field["field_name"] == "expiry_date":
                parsed = parse_date(field["value"]) if isinstance(field["value"], str) else None
                if parsed:
                    doc.expiry_date = parsed
            if field["field_name"] == "issue_date":
                parsed = parse_date(field["value"]) if isinstance(field["value"], str) else None
                if parsed:
                    doc.issue_date = parsed

        if not doc.exclude_from_ai:
            await db.execute(delete(DocumentChunk).where(DocumentChunk.document_id == doc.id))
            for chunk in chunk_text(doc.ocr_text or "", result.get("pages") or []):
                embedding = local_embedding(chunk["text"], settings.embedding_dimensions)
                db.add(
                    DocumentChunk(
                        user_id=doc.user_id,
                        document_id=doc.id,
                        chunk_index=chunk["chunk_index"],
                        text=chunk["text"],
                        page=chunk["page"],
                        extra={"source": "ocr"},
                        embedding=embedding,
                    )
                )

        from app.documents.duplicates import detect_similar
        from app.services.knowledge_graph import upsert_from_document
        from app.services.contradiction import detect_contradictions

        await detect_similar(db, doc)
        await upsert_from_document(db, doc)
        await detect_contradictions(db, doc)

        doc.status = DocumentStatus.READY
        await db.commit()
    except Exception as exc:
        log.exception("processing_failed", document_id=document_id, error=str(exc))
        doc = await db.get(Document, document_id)
        if doc:
            doc.status = DocumentStatus.FAILED
            doc.processing_error = "Processing failed"
            await db.commit()


async def enqueue_document_processing(document_id: str) -> None:
    try:
        from app.workers.celery_app import celery_app

        pinged = celery_app.control.inspect(timeout=0.4).ping()
        if pinged:
            from app.workers.tasks import process_document_task

            process_document_task.delay(document_id)
            return
    except Exception:
        pass
    from app.database import SessionLocal

    async with SessionLocal() as db:
        await process_document(db, document_id)
