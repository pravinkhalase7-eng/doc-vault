"""Revision ID: 0004_family_sharing
Revises: 0003_usage_and_quota
Create Date: 2026-09-03
"""

from alembic import op

revision = "0004_family_sharing"
down_revision = "0003_usage_and_quota"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'family_role') THEN
                CREATE TYPE family_role AS ENUM ('OWNER', 'MEMBER');
            END IF;
        END $$;
        """
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS families (
            id UUID PRIMARY KEY,
            owner_id UUID NOT NULL UNIQUE REFERENCES users(id) ON DELETE CASCADE,
            name VARCHAR(80) NOT NULL DEFAULT 'Family',
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS ix_families_owner_id ON families (owner_id)")
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS family_members (
            id UUID PRIMARY KEY,
            family_id UUID NOT NULL REFERENCES families(id) ON DELETE CASCADE,
            user_id UUID REFERENCES users(id) ON DELETE SET NULL,
            email VARCHAR(255) NOT NULL,
            role family_role NOT NULL DEFAULT 'MEMBER',
            joined_at TIMESTAMPTZ,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            CONSTRAINT uq_family_member_email UNIQUE (family_id, email)
        )
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS ix_family_members_family_id ON family_members (family_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_family_members_user_id ON family_members (user_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_family_members_email ON family_members (email)")
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS family_collection_shares (
            id UUID PRIMARY KEY,
            family_id UUID NOT NULL REFERENCES families(id) ON DELETE CASCADE,
            collection_id UUID NOT NULL REFERENCES collections(id) ON DELETE CASCADE,
            role share_role NOT NULL DEFAULT 'VIEWER',
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            CONSTRAINT uq_family_collection_share UNIQUE (family_id, collection_id)
        )
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS ix_family_collection_shares_family_id ON family_collection_shares (family_id)")
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_family_collection_shares_collection_id ON family_collection_shares (collection_id)"
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS family_collection_shares")
    op.execute("DROP TABLE IF EXISTS family_members")
    op.execute("DROP TABLE IF EXISTS families")
    op.execute("DROP TYPE IF EXISTS family_role")
