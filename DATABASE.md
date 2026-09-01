# Database

PostgreSQL 16 + pgvector. Alembic revision `0001_initial` creates:

users, user_sessions, user_preferences, email_verification_tokens, password_reset_tokens,
categories, document_types, documents, document_versions, document_metadata, tags, document_tags,
document_chunks (vector embeddings), entities, entity_relationships,
collections, collection_documents, tasks, reminders,
shares, share_links, share_link_events,
notifications, email_logs,
ai_conversations, ai_messages, ai_audit_logs, ai_evidence, ai_feedback, ai_proposals,
security_events, storage_usage, backup_records, secure_links

Apply:

```bash
cd backend && alembic upgrade head
```
