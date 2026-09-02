from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BaseModel
from app.models.enums import FamilyRole, ShareRole


class Family(BaseModel):
    __tablename__ = "families"

    owner_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("users.id", ondelete="CASCADE"), unique=True, index=True
    )
    name: Mapped[str] = mapped_column(String(80), default="Family", nullable=False)


class FamilyMember(BaseModel):
    __tablename__ = "family_members"
    __table_args__ = (UniqueConstraint("family_id", "email", name="uq_family_member_email"),)

    family_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("families.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[str | None] = mapped_column(
        UUID(as_uuid=False), ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    email: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    role: Mapped[FamilyRole] = mapped_column(
        Enum(FamilyRole, name="family_role"), default=FamilyRole.MEMBER, nullable=False
    )
    joined_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class FamilyCollectionShare(BaseModel):
    __tablename__ = "family_collection_shares"
    __table_args__ = (UniqueConstraint("family_id", "collection_id", name="uq_family_collection_share"),)

    family_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("families.id", ondelete="CASCADE"), index=True
    )
    collection_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("collections.id", ondelete="CASCADE"), index=True
    )
    role: Mapped[ShareRole] = mapped_column(
        Enum(ShareRole, name="share_role", create_type=False),
        default=ShareRole.VIEWER,
        nullable=False,
    )
