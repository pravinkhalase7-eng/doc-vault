from sqlalchemy import Boolean, Enum, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel
from app.models.enums import AIOperation


class AIConversation(BaseModel):
    __tablename__ = "ai_conversations"

    user_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("users.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(200), default="Ask My Vault")
    language: Mapped[str] = mapped_column(String(8), default="en")

    messages: Mapped[list["AIMessage"]] = relationship(back_populates="conversation", cascade="all, delete-orphan")


class AIMessage(BaseModel):
    __tablename__ = "ai_messages"

    conversation_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("ai_conversations.id", ondelete="CASCADE"), index=True
    )
    role: Mapped[str] = mapped_column(String(16), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    evidence: Mapped[list | None] = mapped_column(JSONB)
    model: Mapped[str | None] = mapped_column(String(80))
    external_ai: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    data_access: Mapped[dict | None] = mapped_column(JSONB)

    conversation: Mapped[AIConversation] = relationship(back_populates="messages")


class AIAuditLog(BaseModel):
    __tablename__ = "ai_audit_logs"

    user_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("users.id", ondelete="CASCADE"), index=True)
    operation: Mapped[AIOperation] = mapped_column(Enum(AIOperation, name="ai_operation"), nullable=False)
    documents_accessed: Mapped[list] = mapped_column(JSONB, default=list)
    tool_called: Mapped[str | None] = mapped_column(String(80))
    model: Mapped[str | None] = mapped_column(String(80))
    external_ai: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    success: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    fields_used: Mapped[list] = mapped_column(JSONB, default=list)
    raw_document_sent: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    privacy_decision: Mapped[str | None] = mapped_column(String(32))
    extra: Mapped[dict | None] = mapped_column("metadata", JSONB)


class AIEvidence(BaseModel):
    __tablename__ = "ai_evidence"

    user_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("users.id", ondelete="CASCADE"), index=True)
    document_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("documents.id", ondelete="CASCADE"), index=True)
    message_id: Mapped[str | None] = mapped_column(UUID(as_uuid=False), ForeignKey("ai_messages.id", ondelete="SET NULL"))
    page_number: Mapped[int | None] = mapped_column(Integer)
    text_reference: Mapped[str] = mapped_column(Text, nullable=False)
    bounding_box: Mapped[dict | None] = mapped_column(JSONB)
    ai_operation: Mapped[AIOperation] = mapped_column(Enum(AIOperation, name="ai_operation", create_type=False))
    confidence: Mapped[float | None] = mapped_column(Float)


class AIFeedback(BaseModel):
    __tablename__ = "ai_feedback"

    user_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("users.id", ondelete="CASCADE"), index=True)
    document_id: Mapped[str | None] = mapped_column(UUID(as_uuid=False), ForeignKey("documents.id", ondelete="SET NULL"))
    message_id: Mapped[str | None] = mapped_column(UUID(as_uuid=False), ForeignKey("ai_messages.id", ondelete="SET NULL"))
    metadata_id: Mapped[str | None] = mapped_column(UUID(as_uuid=False), ForeignKey("document_metadata.id", ondelete="SET NULL"))
    rating: Mapped[str] = mapped_column(String(16), nullable=False)
    corrected_value: Mapped[str | None] = mapped_column(Text)
    field_name: Mapped[str | None] = mapped_column(String(80))
    notes: Mapped[str | None] = mapped_column(Text)


class AIProposal(BaseModel):
    __tablename__ = "ai_proposals"

    user_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("users.id", ondelete="CASCADE"), index=True)
    kind: Mapped[str] = mapped_column(String(40), nullable=False)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False)
    executed_at: Mapped[str | None] = mapped_column(String(40))
