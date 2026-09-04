#!/usr/bin/env bash
# Copy deploy/host-nginx-docvault.conf onto the VPS host nginx.
# Safe to run from Jenkins (host Docker socket) or on the VPS.
set -euo pipefail

DOMAIN="${PUBLIC_HOST:-docvault.doxstation.com}"
DOMAIN="${DOMAIN#https://}"
DOMAIN="${DOMAIN#http://}"
DOMAIN="${DOMAIN%%/*}"
ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
TEMPLATE="${ROOT_DIR}/deploy/host-nginx-docvault.conf"

if [ ! -f "$TEMPLATE" ]; then
  echo "Missing $TEMPLATE"
  exit 1
fi

rendered="$(mktemp)"
trap 'rm -f "$rendered"' EXIT
sed "s/__DOMAIN__/${DOMAIN}/g" "$TEMPLATE" > "$rendered"

echo "Installing host nginx site for ${DOMAIN} from git"

docker run --rm -i \
  -v /etc/nginx/sites-available:/sites-available \
  -v /etc/nginx/sites-enabled:/sites-enabled \
  alpine:3.20 \
  sh -c 'cat > /sites-available/docvault && ln -sfn /sites-available/docvault /sites-enabled/docvault' \
  < "$rendered"

docker run --rm --pid=host \
  -v /run:/host-run:ro \
  alpine:3.20 \
  sh -c 'if [ -f /host-run/nginx.pid ]; then kill -HUP "$(cat /host-run/nginx.pid)"; else echo "Copied site file; reload with: sudo systemctl reload nginx"; fi'

echo "Host nginx reloaded from git (${DOMAIN} → 127.0.0.1:8088)"
