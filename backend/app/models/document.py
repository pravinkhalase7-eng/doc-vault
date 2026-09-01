from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from pgvector.sqlalchemy import Vector

from app.config import get_settings
from app.models.base import BaseModel, SoftDeleteMixin
from app.models.enums import DocumentStatus, SensitivityLevel, VerificationStatus

_settings = get_settings()


class Category(BaseModel, SoftDeleteMixin):
    __tablename__ = "categories"
    __table_args__ = (UniqueConstraint("user_id", "slug", name="uq_category_user_slug"),)

    user_id: Mapped[str | None] = mapped_column(UUID(as_uuid=False), ForeignKey("users.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    slug: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    is_system: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    icon: Mapped[str | None] = mapped_column(String(64))
    sort_order: Mapped[int] = mapped_column(Integer, default=0)


class DocumentType(BaseModel, SoftDeleteMixin):
    __tablename__ = "document_types"
    __table_args__ = (UniqueConstraint("user_id", "slug", name="uq_doctype_user_slug"),)

    user_id: Mapped[str | None] = mapped_column(UUID(as_uuid=False), ForeignKey("users.id", ondelete="CASCADE"), index=True)
    category_id: Mapped[str | None] = mapped_column(UUID(as_uuid=False), ForeignKey("categories.id", ondelete="SET NULL"))
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    slug: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    is_system: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    default_sensitivity: Mapped[SensitivityLevel] = mapped_column(
        Enum(SensitivityLevel, name="sensitivity_level"),
        default=SensitivityLevel.PRIVATE,
        nullable=False,
    )


class Tag(BaseModel):
    __tablename__ = "tags"
    __table_args__ = (UniqueConstraint("user_id", "slug", name="uq_tag_user_slug"),)

    user_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("users.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    slug: Mapped[str] = mapped_column(String(64), nullable=False)


class Document(BaseModel, SoftDeleteMixin):
    __tablename__ = "documents"
    __table_args__ = (
        Index("ix_documents_user_status", "user_id", "status"),
        Index("ix_documents_user_expiry", "user_id", "expiry_date"),
        Index("ix_documents_sha256", "sha256"),
    )

    user_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("users.id", ondelete="CASCADE"), index=True)
    category_id: Mapped[str | None] = mapped_column(UUID(as_uuid=False), ForeignKey("categories.id", ondelete="SET NULL"))
    document_type_id: Mapped[str | None] = mapped_column(
        UUID(as_uuid=False), ForeignKey("document_types.id", ondelete="SET NULL")
    )
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    original_filename: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    subcategory: Mapped[str | None] = mapped_column(String(120))
    related_person: Mapped[str | None] = mapped_column(String(200))
    related_entity: Mapped[str | None] = mapped_column(String(200))
    source: Mapped[str | None] = mapped_column(String(200))
    mime_type: Mapped[str] = mapped_column(String(120), nullable=False)
    extension: Mapped[str] = mapped_column(String(16), nullable=False)
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    perceptual_hash: Mapped[str | None] = mapped_column(String(64))
    storage_key: Mapped[str] = mapped_column(String(512), nullable=False)
    thumbnail_key: Mapped[str | None] = mapped_column(String(512))
    preview_key: Mapped[str | None] = mapped_column(String(512))
    page_count: Mapped[int | None] = mapped_column(Integer)
    status: Mapped[DocumentStatus] = mapped_column(
        Enum(DocumentStatus, name="document_status"), default=DocumentStatus.UPLOADED, nullable=False
    )
    processing_error: Mapped[str | None] = mapped_column(Text)
    sensitivity: Mapped[SensitivityLevel] = mapped_column(
        Enum(SensitivityLevel, name="sensitivity_level", create_type=False),
        default=SensitivityLevel.PRIVATE,
        nullable=False,
    )
    exclude_from_ai: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    ai_classification: Mapped[str | None] = mapped_column(String(120))
    ai_confidence: Mapped[float | None] = mapped_column(Float)
    verification_status: Mapped[VerificationStatus] = mapped_column(
        Enum(VerificationStatus, name="verification_status"),
        default=VerificationStatus.UNVERIFIED,
        nullable=False,
    )
    issue_date: Mapped[date | None] = mapped_column(Date)
    expiry_date: Mapped[date | None] = mapped_column(Date)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    parent_document_id: Mapped[str | None] = mapped_column(UUID(as_uuid=False), ForeignKey("documents.id"))
    ocr_text: Mapped[str | None] = mapped_column(Text)
    encrypted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    trashed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    download_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False, server_default="0")
    share_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False, server_default="0")

    tags: Mapped[list["DocumentTag"]] = relationship(back_populates="document", cascade="all, delete-orphan")
    metadata_fields: Mapped[list["DocumentMetadata"]] = relationship(
        back_populates="document", cascade="all, delete-orphan"
    )
    versions: Mapped[list["DocumentVersion"]] = relationship(
        back_populates="document",
        foreign_keys="DocumentVersion.document_id",
        cascade="all, delete-orphan",
    )


class DocumentVersion(BaseModel):
    __tablename__ = "document_versions"

    document_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("documents.id", ondelete="CASCADE"), index=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    storage_key: Mapped[str] = mapped_column(String(512), nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    note: Mapped[str | None] = mapped_column(String(500))

    document: Mapped[Document] = relationship(back_populates="versions", foreign_keys=[document_id])


class DocumentMetadata(BaseModel):
    __tablename__ = "document_metadata"
    __table_args__ = (Index("ix_doc_meta_user_field", "user_id", "field_name"),)

    user_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("users.id", ondelete="CASCADE"), index=True)
    document_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("documents.id", ondelete="CASCADE"), index=True)
    field_name: Mapped[str] = mapped_column(String(80), nullable=False)
    value: Mapped[str | None] = mapped_column(Text)
    confidence: Mapped[float | None] = mapped_column(Float)
    page: Mapped[int | None] = mapped_column(Integer)
    bounding_box: Mapped[dict | None] = mapped_column(JSONB)
    source: Mapped[str] = mapped_column(String(32), default="ai")
    verification_status: Mapped[VerificationStatus] = mapped_column(
        Enum(VerificationStatus, name="verification_status", create_type=False),
        default=VerificationStatus.UNVERIFIED,
        nullable=False,
    )

    document: Mapped[Document] = relationship(back_populates="metadata_fields")


class DocumentTag(BaseModel):
    __tablename__ = "document_tags"
    __table_args__ = (UniqueConstraint("document_id", "tag_id", name="uq_document_tag"),)

    document_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("documents.id", ondelete="CASCADE"))
    tag_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("tags.id", ondelete="CASCADE"))

    document: Mapped[Document] = relationship(back_populates="tags")
    tag: Mapped[Tag] = relationship()


class DocumentChunk(BaseModel):
    __tablename__ = "document_chunks"
    __table_args__ = (Index("ix_chunks_document_page", "document_id", "page"),)

    user_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("users.id", ondelete="CASCADE"), index=True)
    document_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("documents.id", ondelete="CASCADE"), index=True)
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    page: Mapped[int | None] = mapped_column(Integer)
    token_count: Mapped[int | None] = mapped_column(Integer)
    extra: Mapped[dict | None] = mapped_column("metadata", JSONB)
    embedding = mapped_column(Vector(_settings.embedding_dimensions), nullable=True)
