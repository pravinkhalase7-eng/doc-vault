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


def test_detect_iphone_heic_mif1_brand():
    header = (
        b"\x00\x00\x00\x18"
        b"ftyp"
        b"mif1"
        b"\x00\x00\x00\x00"
        b"heic"
        + b"\x00" * 32
    )
    mime, ext = detect_type(header, "IMG_1001.HEIC")
    assert mime == "image/heic"
    assert ext == ".heic"


def test_detect_heif_by_name_when_magic_is_generic():
    mime, ext = detect_type(b"not a real image but named heif", "scan.heif")
    assert mime == "image/heif"
    assert ext == ".heif"


def test_detect_gif_and_word():
    mime, ext = detect_type(b"GIF89a" + b"\x00" * 20, "loop.gif")
    assert mime == "image/gif"
    assert ext == ".gif"
    zip_docx = b"PK\x03\x04" + b"\x00" * 20
    mime, ext = detect_type(zip_docx, "letter.docx")
    assert mime.endswith("wordprocessingml.document")
    assert ext == ".docx"
    ole = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1" + b"\x00" * 20
    mime, ext = detect_type(ole, "old.doc")
    assert mime == "application/msword"
    assert ext == ".doc"


def test_detect_rejects_exe_and_raw_zip():
    try:
        detect_type(b"MZ\x90\x00", "virus.exe")
        assert False, "should reject"
    except AppError as exc:
        assert exc.code == "UNSUPPORTED_TYPE"
    try:
        detect_type(b"PK\x03\x04" + b"\x00" * 20, "archive.zip")
        assert False, "should reject zip"
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
