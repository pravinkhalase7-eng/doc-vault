from pathlib import Path

from types import SimpleNamespace
from datetime import datetime, UTC

from app.documents.service import serialize_document
from app.exceptions import AppError
from app.models.enums import DocumentStatus, SensitivityLevel, VerificationStatus
from app.storage.local import detect_type, sha256_bytes


def test_detect_pdf_magic():
    mime, ext = detect_type(b"%PDF-1.7 fake", "file.bin")
    assert mime == "application/pdf"
    assert ext == ".pdf"


def test_detect_rejects_exe():
    try:
        detect_type(b"MZ\x90\x00", "virus.exe")
        assert False, "should reject"
    except AppError as exc:
        assert exc.code == "UNSUPPORTED_TYPE"


def test_sha256_stable():
    assert sha256_bytes(b"abc") == sha256_bytes(b"abc")
    assert sha256_bytes(b"abc") != sha256_bytes(b"abd")


def test_serialize_document_without_loaded_tags():
    now = datetime.now(UTC)
    doc = SimpleNamespace(
        id="doc-1",
        title="Passport",
        original_filename="scan.pdf",
        description=None,
        mime_type="application/pdf",
        extension=".pdf",
        size_bytes=12,
        status=DocumentStatus.UPLOADED,
        sensitivity=SensitivityLevel.PRIVATE,
        exclude_from_ai=False,
        category_id=None,
        document_type_id=None,
        ai_classification=None,
        ai_confidence=None,
        verification_status=VerificationStatus.UNVERIFIED,
        issue_date=None,
        expiry_date=None,
        related_person=None,
        page_count=None,
        version=1,
        created_at=now,
        updated_at=now,
        trashed_at=None,
    )
    payload = serialize_document(doc)
    assert payload["id"] == "doc-1"
    assert payload["tags"] == []
    assert payload["status"] == "UPLOADED"
