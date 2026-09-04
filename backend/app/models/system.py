from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BaseModel


class SecurityEvent(BaseModel):
    __tablename__ = "security_events"

    user_id: Mapped[str | None] = mapped_column(UUID(as_uuid=False), ForeignKey("users.id", ondelete="SET NULL"), index=True)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    ip_address: Mapped[str | None] = mapped_column(String(64))
    user_agent: Mapped[str | None] = mapped_column(String(512))
    success: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    detail: Mapped[str | None] = mapped_column(String(500))
    extra: Mapped[dict | None] = mapped_column("metadata", JSONB)


class StorageUsage(BaseModel):
    __tablename__ = "storage_usage"

    user_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("users.id", ondelete="CASCADE"), unique=True)
    used_bytes: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    quota_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    file_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_warning_percent: Mapped[int | None] = mapped_column(Integer)


class BackupRecord(BaseModel):
    __tablename__ = "backup_records"

    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    size_bytes: Mapped[int | None] = mapped_column(BigInteger)
    path: Mapped[str | None] = mapped_column(String(500))
    checksum: Mapped[str | None] = mapped_column(String(128))
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error: Mapped[str | None] = mapped_column(Text)


class SecureLink(BaseModel):
    __tablename__ = "secure_links"

    user_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("users.id", ondelete="CASCADE"), index=True)
    document_id: Mapped[str | None] = mapped_column(UUID(as_uuid=False), ForeignKey("documents.id", ondelete="CASCADE"))
    purpose: Mapped[str] = mapped_column(String(64), nullable=False)
    token_hash: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    one_time: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class InboundMailReceipt(BaseModel):
    __tablename__ = "inbound_mail_receipts"

    fingerprint: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    sender: Mapped[str] = mapped_column(String(320), nullable=False)
    user_id: Mapped[str | None] = mapped_column(UUID(as_uuid=False), ForeignKey("users.id", ondelete="SET NULL"), index=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="accepted")
    detail: Mapped[str | None] = mapped_column(String(200))
