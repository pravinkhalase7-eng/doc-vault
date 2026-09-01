#!/usr/bin/env bash
set -euo pipefail
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
DEST="${BACKUP_DIR:-./backups}/$STAMP"
mkdir -p "$DEST"
umask 077

if command -v pg_dump >/dev/null; then
  pg_dump "${DATABASE_SYNC_URL:-postgresql://docvault:docvault@localhost:5432/docvault}" | gzip > "$DEST/postgres.sql.gz"
fi

STORAGE_ROOT="${STORAGE_ROOT:-/var/lib/docvault}"
if [ -d "$STORAGE_ROOT" ]; then
  tar -C "$(dirname "$STORAGE_ROOT")" -czf "$DEST/files.tar.gz" "$(basename "$STORAGE_ROOT")"
fi

if [ -f .env ]; then
  cp .env "$DEST/app.env"
fi

# Encrypt if ENCRYPTION_KEY is set
if [ -n "${ENCRYPTION_KEY:-}" ] && command -v openssl >/dev/null; then
  tar -C "$DEST" -czf - . | openssl enc -aes-256-cbc -salt -pbkdf2 -pass pass:"$ENCRYPTION_KEY" -out "$DEST.enc"
  rm -rf "$DEST"
  echo "Encrypted backup written to $DEST.enc"
else
  echo "Backup written to $DEST"
fi
