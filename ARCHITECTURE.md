# Architecture

DocVault is a privacy-first personal document OS: a Next.js PWA talks to a FastAPI API, which owns authentication, storage, search, and AI. Gemini never queries PostgreSQL and never reads the filesystem.

```
Internet → Nginx → Next.js PWA
                 → FastAPI /api/v1
                      → PostgreSQL + pgvector
                      → Hostinger disk /var/lib/docvault
                      → Redis → Celery (OCR, embeddings, email, backups)
                      → Privacy Gateway → AIRouter → GeminiProvider | Local
                      → Google ADK DocVaultAgent → ToolPermissionService → services
```

## Backend layers

1. **API routers** (`app/api/v1`) — HTTP, auth dependencies, rate limits
2. **Services** — documents, sharing, search, health, knowledge graph
3. **AI abstraction** — `AIProvider` → `GeminiProvider` / `FutureLocalProvider`
4. **Privacy gateway** — consent, sensitivity, PII, data minimization
5. **ADK tools** — search, reminders, checklists; each call checks `user_id` and document ACLs
6. **Storage** — hashed, typed files on local disk; streaming downloads

## Upload pipeline

Upload → validation → SHA-256 → duplicate check → persist to disk → `UPLOADED` → Celery: OCR → metadata → classify → sensitivity → chunk/embed → user confirmation.

The HTTP upload returns immediately with “Processing document…”.

## Frontend

App Router PWA with mobile-first navigation (Home, Documents, Collections, AI, Notifications, Profile), dark/light/system theme, and an Ask My Vault chat that renders evidence cards.
