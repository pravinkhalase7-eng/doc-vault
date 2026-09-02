"""Revision ID: 0005_reminder_calls
Revises: 0004_family_sharing
Create Date: 2026-09-03
"""

from alembic import op

revision = "0005_reminder_calls"
down_revision = "0004_family_sharing"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE user_preferences ADD COLUMN IF NOT EXISTS phone_number VARCHAR(32)"
    )


def downgrade() -> None:
    op.execute("ALTER TABLE user_preferences DROP COLUMN IF EXISTS phone_number")
