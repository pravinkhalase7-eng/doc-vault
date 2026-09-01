# API

Base: `/api/v1`

Successful payloads: `{ "success": true, "data": ... }`  
Errors: `{ "success": false, "error": { "code": "...", "message": "..." } }`

## Auth

- `POST /auth/register`
- `POST /auth/login`
- `POST /auth/refresh`
- `POST /auth/logout`
- `POST /auth/verify-email`
- `POST /auth/forgot-password`
- `POST /auth/reset-password`
- `POST /auth/2fa/setup` `POST /auth/2fa/enable`

## Documents

- `POST /documents/upload`
- `GET /documents`
- `GET /documents/{id}`
- `PATCH /documents/{id}`
- `DELETE /documents/{id}` (trash)
- `GET /documents/{id}/download`
- `GET /documents/{id}/preview`

## AI

- `POST /ai/chat` — Ask My Vault
- `GET /privacy/center`
- `GET /privacy/activity`
- `DELETE /privacy/ai-data`

## Health

- `GET /health` `/health/db` `/health/redis` `/health/storage` `/health/ai`
