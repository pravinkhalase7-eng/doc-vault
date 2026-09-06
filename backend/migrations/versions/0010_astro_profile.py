"""Revision ID: 0010_astro_profile
Revises: 0009_shared_inbox
Create Date: 2026-09-07
"""

from alembic import op

revision = "0010_astro_profile"
down_revision = "0009_shared_inbox"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE user_preferences ADD COLUMN IF NOT EXISTS birth_name VARCHAR(200)")
    op.execute("ALTER TABLE user_preferences ADD COLUMN IF NOT EXISTS birth_date DATE")
    op.execute("ALTER TABLE user_preferences ADD COLUMN IF NOT EXISTS birth_time VARCHAR(16)")
    op.execute("ALTER TABLE user_preferences ADD COLUMN IF NOT EXISTS birth_place VARCHAR(200)")
    op.execute(
        "ALTER TABLE user_preferences ADD COLUMN IF NOT EXISTS astro_onboarding_dismissed "
        "BOOLEAN NOT NULL DEFAULT FALSE"
    )
    op.execute(
        "ALTER TABLE ai_conversations ADD COLUMN IF NOT EXISTS channel VARCHAR(32) "
        "NOT NULL DEFAULT 'vault'"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_ai_conversations_user_channel "
        "ON ai_conversations (user_id, channel)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_ai_conversations_user_channel")
    op.execute("ALTER TABLE ai_conversations DROP COLUMN IF EXISTS channel")
    op.execute("ALTER TABLE user_preferences DROP COLUMN IF EXISTS astro_onboarding_dismissed")
    op.execute("ALTER TABLE user_preferences DROP COLUMN IF EXISTS birth_place")
    op.execute("ALTER TABLE user_preferences DROP COLUMN IF EXISTS birth_time")
    op.execute("ALTER TABLE user_preferences DROP COLUMN IF EXISTS birth_date")
    op.execute("ALTER TABLE user_preferences DROP COLUMN IF EXISTS birth_name")
