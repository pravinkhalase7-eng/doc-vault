# DocVault AI

A private, AI-powered personal document vault. Originals stay on your Hostinger VPS disk. Google Gemini is optional, server-side only, and never receives files unless you explicitly enable Cloud AI.

## Private AI by design

- Documents are stored under `STORAGE_ROOT` (production: `/var/lib/docvault`)
- Files are served only through authenticated FastAPI endpoints
- Default AI mode is **Private AI** (local OCR, classification, embeddings)
- Highly sensitive types (Aadhaar, PAN, passport, bank, medical) are blocked from Gemini
- Every Cloud AI answer can show evidence: document, page, and what was sent

## Stack

| Layer | Technology |
| --- | --- |
| Frontend | Next.js 16, TypeScript, Tailwind, shadcn/ui, PWA |
| Backend | FastAPI, SQLAlchemy, Alembic, PostgreSQL + pgvector |
| Jobs | Redis, Celery |
| AI | Local processors + Gemini + Google ADK tool layer |

## Quick start (development)

```bash
cp .env.example .env
# start postgres + redis
docker compose up -d postgres redis

cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
alembic upgrade head
uvicorn app.main:app --reload --port 8000

cd ../frontend
npm install
npm run dev
```

Open http://localhost:3000

## Production

See [DEPLOYMENT.md](DEPLOYMENT.md). Use `./scripts/deploy.sh` on the VPS. Mount `/var/lib/docvault` as persistent storage — never keep uploads inside ephemeral containers.

## Documentation

- [ARCHITECTURE.md](ARCHITECTURE.md)
- [SECURITY.md](SECURITY.md)
- [AI_PRIVACY.md](AI_PRIVACY.md)
- [API.md](API.md)
- [DATABASE.md](DATABASE.md)
- [DEPLOYMENT.md](DEPLOYMENT.md)
# doc-vault
# doc-vault
