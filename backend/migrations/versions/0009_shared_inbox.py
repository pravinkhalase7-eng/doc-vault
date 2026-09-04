"""Revision ID: 0009_shared_inbox
Revises: 0008_email_ingest
Create Date: 2026-09-05
"""

from alembic import op

revision = "0009_shared_inbox"
down_revision = "0008_email_ingest"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS inbound_mail_receipts (
            id UUID PRIMARY KEY,
            fingerprint VARCHAR(64) NOT NULL UNIQUE,
            sender VARCHAR(320) NOT NULL,
            user_id UUID REFERENCES users(id) ON DELETE SET NULL,
            status VARCHAR(32) NOT NULL DEFAULT 'accepted',
            detail VARCHAR(200),
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS ix_inbound_mail_receipts_user_id ON inbound_mail_receipts (user_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_inbound_mail_receipts_fingerprint ON inbound_mail_receipts (fingerprint)")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS inbound_mail_receipts")
