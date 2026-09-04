#!/usr/bin/env bash
# Put HTTPS in front of DocVault using the VPS host nginx (doxstation.com already
# owns :443). Run on the VPS as root, after DNS for PUBLIC_HOST points here.
#
#   sudo PUBLIC_HOST=docvault.doxstation.com bash scripts/enable_host_https.sh
#
set -euo pipefail

DOMAIN="${PUBLIC_HOST:-docvault.doxstation.com}"
DOMAIN="${DOMAIN#https://}"
DOMAIN="${DOMAIN#http://}"
DOMAIN="${DOMAIN%%/*}"
EMAIL="${CERTBOT_EMAIL:-}"
SITE_NAME="docvault"
AVAILABLE="/etc/nginx/sites-available/${SITE_NAME}"
ENABLED="/etc/nginx/sites-enabled/${SITE_NAME}"
ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
TEMPLATE="${ROOT_DIR}/deploy/host-nginx-docvault.conf"

if [ "$(id -u)" -ne 0 ]; then
  echo "Run as root: sudo PUBLIC_HOST=${DOMAIN} bash $0"
  exit 1
fi

if [ ! -d /etc/nginx/sites-available ]; then
  echo "Host nginx sites-available not found. This script is for the Ubuntu VPS nginx, not the Jenkins container."
  exit 1
fi

if [ ! -f "$TEMPLATE" ]; then
  echo "Missing template: $TEMPLATE"
  exit 1
fi

echo "=== DNS check for ${DOMAIN} ==="
resolved="$(getent ahostsv4 "$DOMAIN" 2>/dev/null | awk '{print $1; exit}' || true)"
local_ips="$(hostname -I 2>/dev/null || true)"
if [ -z "$resolved" ]; then
  echo "DNS is missing. In Hostinger DNS for doxstation.com add:"
  echo "  Type: A"
  echo "  Name: ${DOMAIN%%.*}"
  echo "  Value: $(echo "$local_ips" | awk '{print $1}')"
  echo "Wait a few minutes, then rerun this script."
  exit 1
fi
match=0
for ip in $local_ips; do
  if [ "$ip" = "$resolved" ]; then
    match=1
    break
  fi
done
if [ "$match" != "1" ]; then
  echo "${DOMAIN} resolves to ${resolved}, which is not this VPS (${local_ips})."
  echo "Fix the A record, then rerun."
  exit 1
fi
echo "DNS OK: ${DOMAIN} -> ${resolved}"

sed "s/__DOMAIN__/${DOMAIN}/g" "$TEMPLATE" > "$AVAILABLE"
ln -sfn "$AVAILABLE" "$ENABLED"
nginx -t
systemctl reload nginx

if ! command -v certbot >/dev/null 2>&1; then
  export DEBIAN_FRONTEND=noninteractive
  apt-get update -qq
  apt-get install -y certbot python3-certbot-nginx
fi

cert_args=(--nginx -d "$DOMAIN" --non-interactive --agree-tos --redirect)
if [ -n "$EMAIL" ]; then
  cert_args+=(--email "$EMAIL")
else
  cert_args+=(--register-unsafely-without-email)
fi

echo "=== Requesting Let's Encrypt certificate ==="
certbot "${cert_args[@]}"
nginx -t
systemctl reload nginx

# Browsers treat HTTP as "Not Secure". Keep HTTPS sticky after the first visit.
if grep -q "listen 443" "$AVAILABLE" && ! grep -q Strict-Transport-Security "$AVAILABLE"; then
  python3 - <<'PY'
from pathlib import Path
path = Path("/etc/nginx/sites-available/docvault")
text = path.read_text()
needle = "server_name docvault.doxstation.com;"
hsts = '    add_header Strict-Transport-Security "max-age=31536000" always;\n'
if "Strict-Transport-Security" not in text and needle in text:
    # insert into the last server block (TLS) before the final closing brace
    idx = text.rfind("server {")
    if idx != -1:
        close = text.rfind("}")
        text = text[:close] + hsts + text[close:]
        path.write_text(text)
PY
  nginx -t && systemctl reload nginx
fi

echo
echo "HTTPS is ready: https://${DOMAIN}"
echo "Keep http://127.0.0.1:8088 for Jenkins. Phones should use the https URL."
echo "Set PUBLIC_HOST=${DOMAIN} in the Jenkins doc-vault.env secret file and rebuild."
