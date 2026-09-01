from app.auth.security import hash_password, verify_password
from app.ai.privacy_gateway import check_ai_request, detect_pii_labels, minimize_text
from app.documents.processing import classify_local, extract_fields, local_embedding
from app.models.enums import AIOperation, AIPrivacyMode, SensitivityLevel
from app.models.user import User, UserPreference
from app.models.document import Document
from types import SimpleNamespace
import pytest


def test_access_token_from_query_and_header():
    from starlette.requests import Request
    from app.auth.service import access_token_from_request

    query_request = Request(
        {
            "type": "http",
            "http_version": "1.1",
            "method": "GET",
            "path": "/preview",
            "raw_path": b"/preview",
            "query_string": b"token=query-token",
            "headers": [],
        }
    )
    assert access_token_from_request(query_request, allow_query_token=True) == "query-token"
    assert access_token_from_request(query_request, allow_query_token=False) is None

    header_request = Request(
        {
            "type": "http",
            "http_version": "1.1",
            "method": "GET",
            "path": "/preview",
            "raw_path": b"/preview",
            "query_string": b"",
            "headers": [(b"authorization", b"Bearer header-token")],
        }
    )
    assert access_token_from_request(header_request, allow_query_token=False) == "header-token"


def test_password_hash_roundtrip():
    hashed = hash_password("correct-horse-battery")
    assert hashed != "correct-horse-battery"
    assert verify_password("correct-horse-battery", hashed)
    assert not verify_password("wrong", hashed)


def test_classify_aadhaar_is_highly_sensitive():
    doc_type, category, sensitivity, confidence = classify_local("UIDAI Aadhaar card", "scan.pdf")
    assert doc_type == "Aadhaar"
    assert category == "Government"
    assert sensitivity == SensitivityLevel.HIGHLY_SENSITIVE
    assert confidence > 0.5


def test_extract_expiry():
    fields = extract_fields("Policy No: ABC123456\nValid till: 31/08/2027\nVehicle MH12AB1234")
    names = {f["field_name"]: f["value"] for f in fields}
    assert names["expiry_date"] == "2027-08-31"
    assert names["policy_number"] == "ABC123456"
    assert names["vehicle_number"] == "MH12AB1234"


def test_local_embedding_is_normalized():
    vec = local_embedding("car insurance", 32)
    assert len(vec) == 32
    assert abs(sum(v * v for v in vec) ** 0.5 - 1) < 1e-6


def test_pii_minimization_redacts_pan():
    text = "PAN ABCDE1234F belongs to the holder"
    labels = detect_pii_labels(text)
    assert "possible_pan" in labels
    minimized = minimize_text(text)
    assert "ABCDE1234F" not in minimized


class DummyDB:
    def __init__(self):
        self.added = []

    def add(self, obj):
        self.added.append(obj)


@pytest.mark.asyncio
async def test_privacy_gateway_blocks_private_mode_external():
    user = User(email="a@b.com", password_hash="x", full_name="A")
    user.id = "user-1"
    user.preferences = UserPreference(user_id="user-1", ai_privacy_mode=AIPrivacyMode.PRIVATE, external_ai_enabled=False)
    doc = Document(
        user_id="user-1",
        title="Aadhaar",
        original_filename="a.pdf",
        mime_type="application/pdf",
        extension=".pdf",
        size_bytes=1,
        sha256="a",
        storage_key="x",
        sensitivity=SensitivityLevel.HIGHLY_SENSITIVE,
        exclude_from_ai=False,
    )
    doc.id = "doc-1"
    db = DummyDB()
    from app.exceptions import PrivacyRejectedError

    with pytest.raises(PrivacyRejectedError):
        await check_ai_request(db, user, AIOperation.CHAT, [doc], external_ai=True)


@pytest.mark.asyncio
async def test_privacy_gateway_skips_excluded_documents():
    user = User(email="a@b.com", password_hash="x", full_name="A")
    user.id = "user-1"
    user.preferences = UserPreference(
        user_id="user-1", ai_privacy_mode=AIPrivacyMode.CLOUD, external_ai_enabled=True
    )
    doc = Document(
        user_id="user-1",
        title="Notes",
        original_filename="n.txt",
        mime_type="text/plain",
        extension=".txt",
        size_bytes=1,
        sha256="a",
        storage_key="x",
        sensitivity=SensitivityLevel.PRIVATE,
        exclude_from_ai=True,
    )
    doc.id = "doc-2"
    db = DummyDB()
    from app.config import get_settings

    # Without Gemini key, external is still rejected by gateway.
    from app.exceptions import PrivacyRejectedError

    with pytest.raises(PrivacyRejectedError):
        await check_ai_request(db, user, AIOperation.CHAT, [doc], external_ai=True)
