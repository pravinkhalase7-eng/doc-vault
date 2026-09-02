from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.collections.service import (
    descendants_of,
    document_ids_for_collections,
    is_default_collection,
    owned_collection,
    parent_map,
    serialize_collection,
)
from app.config import get_settings
from app.email.template_service import send_templated
from app.exceptions import AppError, ConflictError, ForbiddenError, NotFoundError
from app.models.collection import Collection
from app.models.enums import FamilyRole, ShareRole
from app.models.family import Family, FamilyCollectionShare, FamilyMember
from app.models.user import User

settings = get_settings()


def member_visible_ids(share_roots: set[str], parents: dict[str, str | None]) -> set[str]:
    visible = set(share_roots)
    for root in share_roots:
        visible |= descendants_of(root, parents)
    return visible


def rewrite_shared_parent(collection_id: str, parent_id: str | None, visible: set[str]) -> str | None:
    if parent_id and parent_id in visible:
        return parent_id
    return None


async def ensure_family(db: AsyncSession, user: User) -> Family:
    family = await db.scalar(select(Family).where(Family.owner_id == user.id))
    if family:
        await _ensure_owner_member(db, family, user)
        return family
    family = Family(owner_id=user.id, name="Family")
    db.add(family)
    await db.flush()
    db.add(
        FamilyMember(
            family_id=family.id,
            user_id=user.id,
            email=user.email.lower(),
            role=FamilyRole.OWNER,
            joined_at=datetime.now(UTC),
        )
    )
    await db.flush()
    return family


async def _ensure_owner_member(db: AsyncSession, family: Family, user: User) -> None:
    existing = await db.scalar(
        select(FamilyMember).where(FamilyMember.family_id == family.id, FamilyMember.email == user.email.lower())
    )
    if existing:
        existing.user_id = user.id
        existing.role = FamilyRole.OWNER
        if not existing.joined_at:
            existing.joined_at = datetime.now(UTC)
        return
    db.add(
        FamilyMember(
            family_id=family.id,
            user_id=user.id,
            email=user.email.lower(),
            role=FamilyRole.OWNER,
            joined_at=datetime.now(UTC),
        )
    )
    await db.flush()


async def family_ids_for_user(db: AsyncSession, user_id: str) -> list[str]:
    owned = (await db.scalars(select(Family.id).where(Family.owner_id == user_id))).all()
    joined = (
        await db.scalars(
            select(FamilyMember.family_id).where(
                FamilyMember.user_id == user_id,
                FamilyMember.joined_at.is_not(None),
            )
        )
    ).all()
    return list(dict.fromkeys([str(i) for i in owned if i] + [str(i) for i in joined if i]))


async def family_visible_collection_ids(db: AsyncSession, user_id: str) -> set[str]:
    family_ids = await family_ids_for_user(db, user_id)
    if not family_ids:
        return set()
    shares = (
        await db.scalars(select(FamilyCollectionShare).where(FamilyCollectionShare.family_id.in_(family_ids)))
    ).all()
    if not shares:
        return set()
    roots = [str(share.collection_id) for share in shares]
    cols = (await db.scalars(select(Collection).where(Collection.id.in_(roots)))).all()
    by_owner: dict[str, list[str]] = {}
    for col in cols:
        by_owner.setdefault(col.user_id, []).append(col.id)
    visible: set[str] = set()
    for owner_id, owner_roots in by_owner.items():
        parents = await parent_map(db, owner_id)
        visible |= member_visible_ids(set(owner_roots), parents)
    return visible


async def family_document_ids(db: AsyncSession, user_id: str) -> set[str]:
    collection_ids = await family_visible_collection_ids(db, user_id)
    if not collection_ids:
        return set()
    grouped = await document_ids_for_collections(db, list(collection_ids))
    ids: set[str] = set()
    for docs in grouped.values():
        ids.update(docs)
    return ids


async def accessible_collection(db: AsyncSession, user_id: str, collection_id: str) -> Collection:
    col = await db.get(Collection, collection_id)
    if not col:
        raise NotFoundError("COLLECTION_NOT_FOUND", "Collection not found")
    if col.user_id == user_id:
        return col
    visible = await family_visible_collection_ids(db, user_id)
    if collection_id not in visible:
        raise NotFoundError("COLLECTION_NOT_FOUND", "Collection not found")
    return col


async def shared_collection_payloads(db: AsyncSession, user_id: str) -> list[dict]:
    family_ids = await family_ids_for_user(db, user_id)
    if not family_ids:
        return []
    shares = (
        await db.scalars(select(FamilyCollectionShare).where(FamilyCollectionShare.family_id.in_(family_ids)))
    ).all()
    if not shares:
        return []
    root_ids = {str(share.collection_id) for share in shares}
    roots = (await db.scalars(select(Collection).where(Collection.id.in_(root_ids)))).all()
    others = [col for col in roots if col.user_id != user_id]
    if not others:
        return []
    owner_ids = list({col.user_id for col in others})
    owners = (await db.scalars(select(User).where(User.id.in_(owner_ids)))).all()
    owner_names = {owner.id: owner.full_name or owner.email for owner in owners}
    payloads: list[dict] = []
    for owner_id in owner_ids:
        parents = await parent_map(db, owner_id)
        owner_roots = {col.id for col in others if col.user_id == owner_id}
        visible = member_visible_ids(owner_roots, parents)
        rows = (await db.scalars(select(Collection).where(Collection.id.in_(visible)))).all()
        docs_by_col = await document_ids_for_collections(db, [col.id for col in rows])
        for col in rows:
            data = serialize_collection(col, docs_by_col.get(col.id, []))
            data["parent_id"] = rewrite_shared_parent(col.id, col.parent_id, visible)
            data["shared"] = True
            data["shared_with_family"] = False
            data["can_edit"] = False
            data["owner_name"] = owner_names.get(col.user_id)
            payloads.append(data)
    return payloads


async def owned_shared_collection_ids(db: AsyncSession, user_id: str) -> set[str]:
    family = await db.scalar(select(Family).where(Family.owner_id == user_id))
    if not family:
        return set()
    rows = (
        await db.scalars(
            select(FamilyCollectionShare.collection_id).where(FamilyCollectionShare.family_id == family.id)
        )
    ).all()
    return {str(i) for i in rows if i}


def serialize_member(member: FamilyMember, user: User | None) -> dict:
    return {
        "id": member.id,
        "email": member.email,
        "full_name": user.full_name if user else None,
        "role": member.role.value if hasattr(member.role, "value") else member.role,
        "status": "joined" if member.joined_at else "pending",
        "joined_at": member.joined_at,
        "is_owner": member.role == FamilyRole.OWNER,
    }


async def family_snapshot(db: AsyncSession, user: User) -> dict:
    family = await ensure_family(db, user)
    members = (
        await db.scalars(select(FamilyMember).where(FamilyMember.family_id == family.id).order_by(FamilyMember.created_at))
    ).all()
    user_ids = [member.user_id for member in members if member.user_id]
    users = (await db.scalars(select(User).where(User.id.in_(user_ids)))).all() if user_ids else []
    by_id = {row.id: row for row in users}
    shares = (
        await db.scalars(select(FamilyCollectionShare).where(FamilyCollectionShare.family_id == family.id))
    ).all()
    cols = []
    if shares:
        cols = (
            await db.scalars(select(Collection).where(Collection.id.in_([share.collection_id for share in shares])))
        ).all()
    col_names = {col.id: col.name for col in cols}
    joined = (
        await db.scalars(
            select(FamilyMember)
            .where(
                FamilyMember.user_id == user.id,
                FamilyMember.family_id != family.id,
                FamilyMember.joined_at.is_not(None),
            )
        )
    ).all()
    other_families: list[dict] = []
    for membership in joined:
        other = await db.get(Family, membership.family_id)
        if not other:
            continue
        owner = await db.get(User, other.owner_id)
        other_families.append(
            {
                "id": other.id,
                "name": other.name,
                "owner_name": (owner.full_name or owner.email) if owner else None,
                "role": membership.role.value if hasattr(membership.role, "value") else membership.role,
            }
        )
    return {
        "family": {"id": family.id, "name": family.name, "is_owner": True},
        "members": [serialize_member(member, by_id.get(member.user_id) if member.user_id else None) for member in members],
        "collections": [
            {"id": share.collection_id, "name": col_names.get(share.collection_id) or "Folder"} for share in shares
        ],
        "joined_families": other_families,
    }


async def invite_member(db: AsyncSession, user: User, email: str) -> FamilyMember:
    family = await ensure_family(db, user)
    address = email.strip().lower()
    if not address:
        raise AppError("INVALID_EMAIL", "Enter an email address", 400)
    if address == user.email.lower():
        raise AppError("SELF_INVITE", "You are already in this family", 400)
    existing = await db.scalar(
        select(FamilyMember).where(FamilyMember.family_id == family.id, FamilyMember.email == address)
    )
    if existing:
        raise ConflictError("ALREADY_INVITED", "That person is already in your family")
    grantee = await db.scalar(select(User).where(User.email == address, User.deleted_at.is_(None)))
    member = FamilyMember(
        family_id=family.id,
        user_id=grantee.id if grantee else None,
        email=address,
        role=FamilyRole.MEMBER,
        joined_at=datetime.now(UTC) if grantee else None,
    )
    db.add(member)
    await db.commit()
    await db.refresh(member)
    await send_templated(
        address,
        "family_invite",
        f"{user.full_name or 'A family member'} invited you to DocVault",
        inviter=user.full_name or user.email,
        link=f"{settings.app_url}/family" if grantee else f"{settings.app_url}/register",
        has_account=bool(grantee),
    )
    return member


async def remove_member(db: AsyncSession, user: User, member_id: str) -> None:
    family = await ensure_family(db, user)
    member = await db.get(FamilyMember, member_id)
    if not member or member.family_id != family.id:
        raise NotFoundError("MEMBER_NOT_FOUND", "Family member not found")
    if member.role == FamilyRole.OWNER or member.user_id == user.id:
        raise ForbiddenError("CANNOT_REMOVE_OWNER", "You cannot remove the family owner")
    await db.delete(member)
    await db.commit()


async def leave_family(db: AsyncSession, user: User, family_id: str) -> None:
    family = await db.get(Family, family_id)
    if not family:
        raise NotFoundError("FAMILY_NOT_FOUND", "Family not found")
    if family.owner_id == user.id:
        raise ForbiddenError("OWNER_CANNOT_LEAVE", "Create a new family instead of leaving your own")
    member = await db.scalar(
        select(FamilyMember).where(FamilyMember.family_id == family_id, FamilyMember.user_id == user.id)
    )
    if not member:
        raise NotFoundError("MEMBER_NOT_FOUND", "You are not in that family")
    await db.delete(member)
    await db.commit()


async def share_collection_with_family(db: AsyncSession, user: User, collection_id: str) -> dict:
    col = await owned_collection(db, user.id, collection_id)
    if is_default_collection(col):
        raise AppError("DEFAULT_NOT_SHAREABLE", "Share a specific folder instead of Default", 400)
    family = await ensure_family(db, user)
    existing = await db.scalar(
        select(FamilyCollectionShare).where(
            FamilyCollectionShare.family_id == family.id,
            FamilyCollectionShare.collection_id == col.id,
        )
    )
    if existing:
        return {"shared": True, "collection_id": col.id, "name": col.name}
    db.add(
        FamilyCollectionShare(
            family_id=family.id,
            collection_id=col.id,
            role=ShareRole.VIEWER,
        )
    )
    await db.commit()
    return {"shared": True, "collection_id": col.id, "name": col.name}


async def unshare_collection_with_family(db: AsyncSession, user: User, collection_id: str) -> None:
    family = await ensure_family(db, user)
    rec = await db.scalar(
        select(FamilyCollectionShare).where(
            FamilyCollectionShare.family_id == family.id,
            FamilyCollectionShare.collection_id == collection_id,
        )
    )
    if rec:
        await db.delete(rec)
        await db.commit()


async def claim_family_invites(db: AsyncSession, user: User) -> None:
    rows = (
        await db.scalars(
            select(FamilyMember).where(
                FamilyMember.email == user.email.lower(),
                or_(FamilyMember.user_id.is_(None), FamilyMember.user_id == user.id),
            )
        )
    ).all()
    now = datetime.now(UTC)
    for member in rows:
        member.user_id = user.id
        if not member.joined_at:
            member.joined_at = now
