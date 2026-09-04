from datetime import UTC, datetime, timedelta
from secrets import token_urlsafe

from fastapi import APIRouter, Depends
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.security import hash_password, hash_token
from app.auth.service import get_current_user
from app.config import get_settings
from app.database import get_db
from app.documents.service import get_document_for_user
from app.email.template_service import send_templated
from app.exceptions import AppError, ForbiddenError, NotFoundError
from app.models.document import Document
from app.models.enums import ShareRole
from app.models.sharing import Share, ShareLink, ShareLinkEvent
from app.models.user import User
from app.schemas.common import ShareCreate, ShareLinkCreate
from app.storage.local import content_disposition_header, stored_file_path

router = APIRouter(prefix="/sharing", tags=["sharing"])
settings = get_settings()


def ok(data):
    return {"success": True, "data": data}


async def valid_share_link(db: AsyncSession, token: str, *, count_view: bool) -> ShareLink:
    rec = await db.scalar(select(ShareLink).where(ShareLink.token_hash == hash_token(token)))
    if not rec or rec.revoked_at:
        raise NotFoundError("LINK_INVALID", "Share link is invalid")
    if rec.expires_at and rec.expires_at < datetime.now(UTC):
        raise ForbiddenError("LINK_EXPIRED", "Share link has expired")
    if rec.max_views is not None and rec.view_count >= rec.max_views:
        raise ForbiddenError("LINK_EXHAUSTED", "Share link view limit reached")
    if count_view:
        rec.view_count += 1
        db.add(ShareLinkEvent(share_link_id=rec.id, event="opened"))
        await db.commit()
    return rec


@router.post("")
async def share(payload: ShareCreate, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    if payload.document_id:
        await get_document_for_user(db, user.id, payload.document_id, require_owner=True)
    grantee = await db.scalar(select(User).where(User.email == payload.email.lower(), User.deleted_at.is_(None)))
    if not grantee:
        raise NotFoundError("USER_NOT_FOUND", "No DocVault user with that email")
    rec = Share(
        owner_id=user.id,
        grantee_id=grantee.id,
        document_id=payload.document_id,
        collection_id=payload.collection_id,
        role=ShareRole(payload.role),
    )
    db.add(rec)
    await db.commit()
    await send_templated(
        grantee.email,
        "document_shared",
        "A document was shared with you",
        link=f"{settings.app_url}/documents/{payload.document_id or ''}",
    )
    return ok({"shared": True, "grantee_id": grantee.id})


@router.get("")
async def list_shares(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    rows = (await db.scalars(select(Share).where(Share.owner_id == user.id, Share.revoked_at.is_(None)))).all()
    return ok(
        [
            {
                "id": s.id,
                "grantee_id": s.grantee_id,
                "document_id": s.document_id,
                "collection_id": s.collection_id,
                "role": s.role.value,
            }
            for s in rows
        ]
    )


@router.delete("/{share_id}")
async def revoke_share(share_id: str, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    rec = await db.get(Share, share_id)
    if not rec or rec.owner_id != user.id:
        raise ForbiddenError()
    rec.revoked_at = datetime.now(UTC)
    await db.commit()
    return ok({"revoked": True})


@router.get("/links")
async def list_links(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    rows = (
        await db.scalars(
            select(ShareLink).where(ShareLink.user_id == user.id, ShareLink.revoked_at.is_(None)).order_by(ShareLink.created_at.desc())
        )
    ).all()
    return ok(
        [
            {
                "id": rec.id,
                "document_id": rec.document_id,
                "collection_id": rec.collection_id,
                "expires_at": rec.expires_at,
                "download_allowed": rec.download_allowed,
                "view_count": rec.view_count,
            }
            for rec in rows
        ]
    )


@router.post("/links")
async def create_link(
    payload: ShareLinkCreate, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    if payload.document_id:
        doc = await get_document_for_user(db, user.id, payload.document_id, require_owner=True)
        doc.share_count = (doc.share_count or 0) + 1
    raw = token_urlsafe(24)
    link = ShareLink(
        user_id=user.id,
        document_id=payload.document_id,
        collection_id=payload.collection_id,
        token_hash=hash_token(raw),
        password_hash=hash_password(payload.password) if payload.password else None,
        expires_at=datetime.now(UTC) + timedelta(hours=payload.expires_hours),
        max_views=payload.max_views,
        download_allowed=payload.download_allowed,
        view_only=not payload.download_allowed,
    )
    db.add(link)
    await db.flush()
    db.add(ShareLinkEvent(share_link_id=link.id, event="created"))
    await db.commit()
    return ok({"token": raw, "url": f"{settings.app_url}/share/{raw}", "expires_at": link.expires_at})


@router.get("/links/{token}")
async def open_link(token: str, db: AsyncSession = Depends(get_db)):
    rec = await valid_share_link(db, token, count_view=True)
    doc = await db.get(Document, rec.document_id) if rec.document_id else None
    if rec.document_id and not doc:
        raise NotFoundError("FILE_MISSING", "Shared file is no longer available")
    return ok(
        {
            "document_id": rec.document_id,
            "title": doc.title if doc else None,
            "original_filename": doc.original_filename if doc else None,
            "mime_type": doc.mime_type if doc else None,
            "download_allowed": rec.download_allowed,
            "view_only": rec.view_only,
        }
    )


@router.get("/links/{token}/file")
async def shared_file(token: str, db: AsyncSession = Depends(get_db), download: bool = False):
    rec = await valid_share_link(db, token, count_view=False)
    if not rec.document_id:
        raise NotFoundError("FILE_MISSING", "This link has no file")
    doc = await db.get(Document, rec.document_id)
    if not doc:
        raise NotFoundError("FILE_MISSING", "Shared file is no longer available")
    path = stored_file_path(doc.storage_key)
    as_attachment = download and rec.download_allowed
    disposition = "attachment" if as_attachment else "inline"
    return FileResponse(
        path,
        media_type=doc.mime_type or "application/octet-stream",
        headers={"Content-Disposition": content_disposition_header(disposition, doc.original_filename)},
    )
