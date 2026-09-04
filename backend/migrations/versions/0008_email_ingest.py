"""Revision ID: 0008_email_ingest
Revises: 0007_google_auth
Create Date: 2026-09-05
"""

from alembic import op

revision = "0008_email_ingest"
down_revision = "0007_google_auth"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE user_preferences ADD COLUMN IF NOT EXISTS email_ingest_token VARCHAR(32)")
    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS ix_user_preferences_email_ingest_token
        ON user_preferences (email_ingest_token)
        WHERE email_ingest_token IS NOT NULL
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_user_preferences_email_ingest_token")
    op.execute("ALTER TABLE user_preferences DROP COLUMN IF EXISTS email_ingest_token")
