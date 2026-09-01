#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
cp -n .env.example .env || true
mkdir -p /var/lib/docvault
docker compose build
docker compose run --rm backend alembic upgrade head
docker compose up -d
echo "DocVault is starting. Configure TLS certificates in nginx/certs."
