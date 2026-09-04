from datetime import UTC, datetime, timedelta

import jwt
import pytest

from app.auth.google import _google_profile_from_idinfo, decode_oauth_state, encode_oauth_state, safe_next
from app.auth.security import verify_password
from app.config import get_settings
from app.exceptions import UnauthorizedError


def test_safe_next_rejects_open_redirects():
    assert safe_next("/home") == "/home"
    assert safe_next("/expiring") == "/expiring"
    assert safe_next("https://evil.example") == "/home"
    assert safe_next("//evil.example") == "/home"
    assert safe_next(r"/\evil") == "/home"
    assert safe_next(None) == "/home"


def test_oauth_state_roundtrip():
    token = encode_oauth_state("/expiring")
    assert decode_oauth_state(token) == "/expiring"


def test_oauth_state_rejects_wrong_type():
    settings = get_settings()
    bad = jwt.encode(
        {
            "type": "access",
            "next": "/admin",
            "exp": int((datetime.now(UTC) + timedelta(minutes=5)).timestamp()),
        },
        settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
    )
    with pytest.raises(UnauthorizedError):
        decode_oauth_state(bad)


def test_google_profile_requires_verified_email():
    with pytest.raises(UnauthorizedError):
        _google_profile_from_idinfo({"sub": "123", "email": "a@b.com", "email_verified": False})
    profile = _google_profile_from_idinfo(
        {"sub": "123", "email": "A@B.com", "email_verified": True, "name": "Ada"}
    )
    assert profile["email"] == "a@b.com"
    assert profile["full_name"] == "Ada"


def test_verify_password_handles_missing_hash():
    assert verify_password("secret", None) is False
