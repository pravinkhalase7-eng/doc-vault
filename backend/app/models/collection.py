from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel
from app.models.enums import AIOperation, ShareRole, TaskStatus


class Collection(BaseModel):
    __tablename__ = "collections"

    user_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("users.id", ondelete="CASCADE"), index=True)
    parent_id: Mapped[str | None] = mapped_column(
        UUID(as_uuid=False), ForeignKey("collections.id", ondelete="SET NULL"), index=True
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    ai_context: Mapped[str | None] = mapped_column(Text)
    goal_key: Mapped[str | None] = mapped_column(String(64))
    is_ai_proposed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    extra: Mapped[dict | None] = mapped_column("metadata", JSONB, default=dict)


class CollectionDocument(BaseModel):
    __tablename__ = "collection_documents"
    __table_args__ = (UniqueConstraint("collection_id", "document_id", name="uq_collection_document"),)

    collection_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("collections.id", ondelete="CASCADE"))
    document_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("documents.id", ondelete="CASCADE"))


class Task(BaseModel):
    __tablename__ = "tasks"

    user_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("users.id", ondelete="CASCADE"), index=True)
    collection_id: Mapped[str | None] = mapped_column(UUID(as_uuid=False), ForeignKey("collections.id", ondelete="SET NULL"))
    document_id: Mapped[str | None] = mapped_column(UUID(as_uuid=False), ForeignKey("documents.id", ondelete="SET NULL"))
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    status: Mapped[TaskStatus] = mapped_column(Enum(TaskStatus, name="task_status"), default=TaskStatus.OPEN, nullable=False)
    due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_by_ai: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


class Reminder(BaseModel):
    __tablename__ = "reminders"

    user_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("users.id", ondelete="CASCADE"), index=True)
    document_id: Mapped[str | None] = mapped_column(UUID(as_uuid=False), ForeignKey("documents.id", ondelete="CASCADE"))
    collection_id: Mapped[str | None] = mapped_column(UUID(as_uuid=False), ForeignKey("collections.id", ondelete="CASCADE"))
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    offset_days: Mapped[int] = mapped_column(Integer, nullable=False)
    fire_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    channel: Mapped[str] = mapped_column(String(32), default="email")
    extra: Mapped[dict | None] = mapped_column("metadata", JSONB)
