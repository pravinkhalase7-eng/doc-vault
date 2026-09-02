"""Persist VAPID keys on disk so workers share the same pair without putting them in git."""

from __future__ import annotations

import json
import os
from pathlib import Path

from app.config import get_settings


def _generate() -> tuple[str, str]:
    import base64

    from cryptography.hazmat.backends import default_backend
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import ec

    key = ec.generate_private_key(ec.SECP256R1(), default_backend())
    private = key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode()
    numbers = key.public_key().public_numbers()
    raw = b"\x04" + numbers.x.to_bytes(32, "big") + numbers.y.to_bytes(32, "big")
    public = base64.urlsafe_b64encode(raw).decode().rstrip("=")
    return public, private


def resolved_vapid_keys() -> tuple[str, str]:
    settings = get_settings()
    if settings.vapid_public_key and settings.vapid_private_key:
        return settings.vapid_public_key.strip(), settings.vapid_private_key.replace("\\n", "\n").strip()
    root = Path(settings.storage_root)
    root.mkdir(parents=True, exist_ok=True)
    path = root / "vapid.json"
    if path.exists():
        data = json.loads(path.read_text())
        return str(data["public"]), str(data["private"])
    public, private = _generate()
    payload = json.dumps({"public": public, "private": private})
    try:
        fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        try:
            os.write(fd, payload.encode())
        finally:
            os.close(fd)
        return public, private
    except FileExistsError:
        data = json.loads(path.read_text())
        return str(data["public"]), str(data["private"])
