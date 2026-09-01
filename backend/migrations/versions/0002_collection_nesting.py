"""Revision ID: 0002_collection_nesting
Revises: 0001_initial
Create Date: 2026-09-01
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0002_collection_nesting"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("collections", sa.Column("parent_id", postgresql.UUID(as_uuid=False), nullable=True))
    op.add_column("collections", sa.Column("ai_context", sa.Text(), nullable=True))
    op.create_foreign_key(
        "fk_collections_parent_id",
        "collections",
        "collections",
        ["parent_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_collections_parent_id", "collections", ["parent_id"])


def downgrade() -> None:
    op.drop_index("ix_collections_parent_id", table_name="collections")
    op.drop_constraint("fk_collections_parent_id", "collections", type_="foreignkey")
    op.drop_column("collections", "ai_context")
    op.drop_column("collections", "parent_id")
