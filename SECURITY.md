# Security

- Passwords hashed with Argon2
- JWT access tokens (15m) + rotating refresh tokens stored as SHA-256 hashes
- Optional TOTP 2FA
- Email verification and password reset tokens hashed at rest
- CORS allowlist, security headers, request IDs
- Rate limits on login, password reset, upload, and AI chat
- Upload validation: size, extension, MIME, magic bytes, path traversal protection
- Downloads authorize ownership or share grants; filesystem paths are never returned
- Soft-delete trash (30 days) before permanent deletion
- Structured logs redact passwords, tokens, and document bodies
- Secrets come from environment variables only

## Isolation tests that must stay green

- User A cannot read User B documents
- AI tools reject foreign `user_id`
- Excluded documents are omitted from search/chat
- Expired share links fail
- Deleted files cannot be downloaded
