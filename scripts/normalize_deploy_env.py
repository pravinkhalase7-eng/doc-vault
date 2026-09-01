#!/usr/bin/env python3
"""Normalize a DocVault env file for Docker Compose deploys."""

from __future__ import annotations

import argparse
import re
from pathlib import Path


def upsert(text: str, key: str, value: str) -> str:
    pattern = re.compile(rf"^{re.escape(key)}=.*$", re.M)
    line = f"{key}={value}"
    if pattern.search(text):
        return pattern.sub(lambda _m: line, text)
    return text.rstrip() + "\n" + line + "\n"


def read_value(text: str, key: str, default: str = "") -> str:
    match = re.search(rf"^{re.escape(key)}=(.*)$", text, re.M)
    if not match:
        return default
    return match.group(1).strip().strip("'").strip('"')


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("env_file")
    parser.add_argument("--public-api-url", default="")
    args = parser.parse_args()

    path = Path(args.env_file)
    text = path.read_text()

    text = text.replace("localhost:5432", "postgres:5432")
    text = text.replace("127.0.0.1:5432", "postgres:5432")
    text = text.replace("localhost:6379", "redis:6379")
    text = text.replace("127.0.0.1:6379", "redis:6379")

    user = read_value(text, "POSTGRES_USER", "docvault")
    password = read_value(text, "POSTGRES_PASSWORD", "docvault")
    db = read_value(text, "POSTGRES_DB", "docvault")
    text = upsert(
        text,
        "DATABASE_URL",
        f"postgresql+asyncpg://{user}:{password}@postgres:5432/{db}",
    )
    text = upsert(
        text,
        "DATABASE_SYNC_URL",
        f"postgresql://{user}:{password}@postgres:5432/{db}",
    )
    text = upsert(text, "REDIS_URL", "redis://redis:6379/0")
    text = upsert(text, "CELERY_BROKER_URL", "redis://redis:6379/1")
    text = upsert(text, "CELERY_RESULT_BACKEND", "redis://redis:6379/2")
    text = upsert(text, "STORAGE_ROOT", "/var/lib/docvault")

    public = (args.public_api_url or "").strip()
    if public:
        origin = public
        if origin.endswith("/api/v1"):
            origin = origin[: -len("/api/v1")]
        origin = origin.rstrip("/")
        text = upsert(text, "NEXT_PUBLIC_API_URL", public)
        text = upsert(text, "API_URL", origin)
        text = upsert(text, "APP_URL", origin.replace(":8000", "") if ":8000" in origin else origin)
        cors = read_value(text, "CORS_ORIGINS")
        extras = [origin]
        if origin.startswith("http://"):
            extras.append("https://" + origin[len("http://") :])
        merged = []
        for item in (cors.split(",") if cors else []) + extras:
            item = item.strip()
            if item and item not in merged:
                merged.append(item)
        text = upsert(text, "CORS_ORIGINS", ",".join(merged))

    path.write_text(text if text.endswith("\n") else text + "\n")


if __name__ == "__main__":
    main()
