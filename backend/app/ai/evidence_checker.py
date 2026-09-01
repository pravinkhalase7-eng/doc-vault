"""Refuse hallucinated answers that cannot be grounded in retrieved evidence."""

from __future__ import annotations

from app.models.document import Document


MISSING = "I couldn't find this information in your documents."


def _file_fields(doc: Document) -> dict:
    return {
        "document_id": doc.id,
        "document_title": doc.title,
        "original_filename": doc.original_filename,
        "mime_type": doc.mime_type,
        "size_bytes": doc.size_bytes,
    }


def validate_answer(answer: str, documents: list[Document], context_records: list[dict]) -> tuple[str, list[dict]]:
    if not documents and not context_records:
        return MISSING, []
    evidence = []
    lower = answer.lower()
    by_id = {doc.id: doc for doc in documents}
    for doc in documents:
        if doc.title and doc.title.lower().split(" ")[0] in lower:
            evidence.append(
                {
                    **_file_fields(doc),
                    "page_number": 1,
                    "text_reference": (doc.ocr_text or doc.title)[:280],
                    "confidence": doc.ai_confidence,
                }
            )
    if not evidence:
        for rec in context_records[:8]:
            doc = by_id.get(rec.get("id"))
            evidence.append(
                {
                    **(_file_fields(doc) if doc else {
                        "document_id": rec["id"],
                        "document_title": rec["title"],
                        "original_filename": rec.get("original_filename") or rec["title"],
                        "mime_type": rec.get("mime_type"),
                        "size_bytes": rec.get("size_bytes"),
                    }),
                    "page_number": 1,
                    "text_reference": rec.get("snippet") or rec["title"],
                    "confidence": 0.6,
                }
            )
    if "i couldn't find" in lower or "could not find" in lower:
        return answer, evidence
    return answer, evidence
