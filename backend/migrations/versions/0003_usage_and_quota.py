"""Revision ID: 0003_usage_and_quota
Revises: 0002_collection_nesting
Create Date: 2026-09-01
"""

from alembic import op

revision = "0003_usage_and_quota"
down_revision = "0002_collection_nesting"
branch_labels = None
depends_on = None

ACCOUNT_QUOTA_BYTES = 104_857_600


def upgrade() -> None:
    op.execute("ALTER TABLE documents ADD COLUMN IF NOT EXISTS download_count INTEGER NOT NULL DEFAULT 0")
    op.execute("ALTER TABLE documents ADD COLUMN IF NOT EXISTS share_count INTEGER NOT NULL DEFAULT 0")
    op.execute(f"UPDATE storage_usage SET quota_bytes = {ACCOUNT_QUOTA_BYTES}")


def downgrade() -> None:
    op.execute("ALTER TABLE documents DROP COLUMN IF EXISTS share_count")
    op.execute("ALTER TABLE documents DROP COLUMN IF EXISTS download_count")
