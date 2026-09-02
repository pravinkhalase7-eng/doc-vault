"""Revision ID: 0002_collection_nesting
Revises: 0001_initial
Create Date: 2026-09-01
"""

from alembic import op

revision = "0002_collection_nesting"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 0001_initial uses metadata.create_all() against the current models, which
    # already include these columns. Keep this revision idempotent so upgrades
    # succeed on databases that ran 0001 with the nested-collection schema.
    op.execute("ALTER TABLE collections ADD COLUMN IF NOT EXISTS parent_id UUID")
    op.execute("ALTER TABLE collections ADD COLUMN IF NOT EXISTS ai_context TEXT")
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_constraint
                WHERE conrelid = 'collections'::regclass
                  AND contype = 'f'
                  AND conname IN ('fk_collections_parent_id', 'collections_parent_id_fkey')
            ) THEN
                ALTER TABLE collections
                    ADD CONSTRAINT fk_collections_parent_id
                    FOREIGN KEY (parent_id) REFERENCES collections(id) ON DELETE SET NULL;
            END IF;
        END $$;
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS ix_collections_parent_id ON collections (parent_id)")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_collections_parent_id")
    op.execute(
        """
        ALTER TABLE collections
            DROP CONSTRAINT IF EXISTS fk_collections_parent_id,
            DROP CONSTRAINT IF EXISTS collections_parent_id_fkey
        """
    )
    op.execute("ALTER TABLE collections DROP COLUMN IF EXISTS ai_context")
    op.execute("ALTER TABLE collections DROP COLUMN IF EXISTS parent_id")
