"""Jenkins smoke check: API process starts and /api/v1/health responds."""

from __future__ import annotations

import os
import sys

os.environ.setdefault("SECRET_KEY", "jenkins-smoke-secret-key")
os.environ.setdefault("JWT_SECRET", "jenkins-smoke-jwt-secret")
os.environ.setdefault("ENCRYPTION_KEY", "jenkins-smoke-encryption-key")
os.environ.setdefault("APP_ENV", "development")
os.environ.setdefault("DEBUG", "false")
os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+asyncpg://docvault:docvault@127.0.0.1:1/docvault",
)
os.environ.setdefault(
    "DATABASE_SYNC_URL",
    "postgresql://docvault:docvault@127.0.0.1:1/docvault",
)

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402


def main() -> int:
    with TestClient(app) as client:
        response = client.get("/api/v1/health")
    if response.status_code != 200:
        print(f"FAIL health status={response.status_code} body={response.text}", file=sys.stderr)
        return 1
    body = response.json()
    if body.get("success") is not True:
        print(f"FAIL health payload={body}", file=sys.stderr)
        return 1
    print("smoke ok", body)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
