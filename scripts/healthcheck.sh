#!/usr/bin/env bash
set -euo pipefail
API="${API_URL:-http://localhost:8000}"
fail=0
for path in /api/v1/health /api/v1/health/db /api/v1/health/storage; do
  if ! curl -fsS "$API$path" >/dev/null; then
    echo "FAIL $path"
    fail=1
  else
    echo "OK   $path"
  fi
done
exit $fail
