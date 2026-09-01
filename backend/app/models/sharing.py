from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BaseModel
from app.models.enums import ShareRole


class Share(BaseModel):
    __tablename__ = "shares"

    owner_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("users.id", ondelete="CASCADE"), index=True)
    grantee_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("users.id", ondelete="CASCADE"), index=True)
    document_id: Mapped[str | None] = mapped_column(UUID(as_uuid=False), ForeignKey("documents.id", ondelete="CASCADE"))
    collection_id: Mapped[str | None] = mapped_column(UUID(as_uuid=False), ForeignKey("collections.id", ondelete="CASCADE"))
    role: Mapped[ShareRole] = mapped_column(Enum(ShareRole, name="share_role"), default=ShareRole.VIEWER, nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ShareLink(BaseModel):
    __tablename__ = "share_links"

    user_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("users.id", ondelete="CASCADE"), index=True)
    document_id: Mapped[str | None] = mapped_column(UUID(as_uuid=False), ForeignKey("documents.id", ondelete="CASCADE"))
    collection_id: Mapped[str | None] = mapped_column(UUID(as_uuid=False), ForeignKey("collections.id", ondelete="CASCADE"))
    token_hash: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    password_hash: Mapped[str | None] = mapped_column(String(255))
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    max_views: Mapped[int | None] = mapped_column(Integer)
    view_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    download_allowed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    view_only: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ShareLinkEvent(BaseModel):
    __tablename__ = "share_link_events"

    share_link_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("share_links.id", ondelete="CASCADE"), index=True
    )
    event: Mapped[str] = mapped_column(String(32), nullable=False)
    ip_address: Mapped[str | None] = mapped_column(String(64))
    user_agent: Mapped[str | None] = mapped_column(String(512))
