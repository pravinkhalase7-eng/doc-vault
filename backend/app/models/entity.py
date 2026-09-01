from sqlalchemy import Enum, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BaseModel
from app.models.enums import EntityKind, RelationshipType


class Entity(BaseModel):
    __tablename__ = "entities"
    __table_args__ = (UniqueConstraint("user_id", "kind", "name", name="uq_entity_user_kind_name"),)

    user_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("users.id", ondelete="CASCADE"), index=True)
    kind: Mapped[EntityKind] = mapped_column(Enum(EntityKind, name="entity_kind"), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    extra: Mapped[dict | None] = mapped_column("metadata", JSONB)


class EntityRelationship(BaseModel):
    __tablename__ = "entity_relationships"

    user_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("users.id", ondelete="CASCADE"), index=True)
    from_entity_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("entities.id", ondelete="CASCADE"))
    to_entity_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("entities.id", ondelete="CASCADE"))
    relation: Mapped[RelationshipType] = mapped_column(
        Enum(RelationshipType, name="relationship_type"), nullable=False
    )
    document_id: Mapped[str | None] = mapped_column(UUID(as_uuid=False), ForeignKey("documents.id", ondelete="SET NULL"))
    extra: Mapped[dict | None] = mapped_column("metadata", JSONB)
