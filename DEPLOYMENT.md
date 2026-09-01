# Deployment (Hostinger VPS)

1. Provision Ubuntu, Docker, and a persistent disk at `/var/lib/docvault`
2. Clone this repository
3. Copy `.env.example` to `.env` and set `JWT_SECRET`, `SECRET_KEY`, SMTP, and optional `GEMINI_API_KEY`
4. Place TLS certificates in `nginx/certs/` if terminating TLS on the VPS (enable HTTPS in Nginx)
5. Run `./scripts/deploy.sh`
6. Run `./scripts/healthcheck.sh`
7. Schedule `./scripts/backup.sh` via cron

Uploads are bind-mounted to `/var/lib/docvault`. Do not store documents in container layers.

Gemini keys stay on the backend. Never put `GEMINI_API_KEY` in `NEXT_PUBLIC_*` variables.
