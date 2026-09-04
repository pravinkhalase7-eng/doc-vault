"""Store a private inbound address and turn forwarded mail into vault uploads."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.auth.service import log_security_event
from app.collections.service import place_uploaded_document
from app.config import get_settings
from app.documents.service import create_upload, serialize_document
from app.email.ingest import (
    InboundMail,
    MAX_ATTACHMENTS,
    generate_ingest_token,
    ingest_address_for,
    keep_attachment,
    match_collection_for_ingest,
    parse_ingest_recipient,
)
from app.email.notification_service import notify
from app.exceptions import AppError
from app.logging import get_logger
from app.models.collection import Collection
from app.models.user import User, UserPreference

log = get_logger("email.ingest")
settings = get_settings()


async def ensure_ingest_token(db: AsyncSession, user: User) -> str:
    prefs = user.preferences
    if prefs and prefs.email_ingest_token:
        return prefs.email_ingest_token
    if not prefs:
        raise AppError("PREFERENCES_MISSING", "User preferences are not ready", 500)
    for _ in range(8):
        token = generate_ingest_token()
        taken = await db.scalar(select(UserPreference.id).where(UserPreference.email_ingest_token == token))
        if taken:
            continue
        prefs.email_ingest_token = token
        await db.commit()
        await db.refresh(prefs)
        return token
    raise AppError("INGEST_TOKEN", "Could not allocate an inbox address", 500)


async def rotate_ingest_token(db: AsyncSession, user: User) -> str:
    prefs = user.preferences
    if not prefs:
        raise AppError("PREFERENCES_MISSING", "User preferences are not ready", 500)
    prefs.email_ingest_token = None
    await db.flush()
    return await ensure_ingest_token(db, user)


async def ingest_status(db: AsyncSession, user: User) -> dict:
    token = await ensure_ingest_token(db, user)
    return {
        "address": ingest_address_for(token),
        "domain": settings.inbound_mail_domain,
        "receiving": settings.inbound_webhook_enabled,
        "hint": "Put the collection name in the subject — Insurance, Bills — or it goes to Default.",
    }


async def user_for_ingest_token(db: AsyncSession, token: str) -> User | None:
    needle = (token or "").strip().lower()
    if not needle:
        return None
    return await db.scalar(
        select(User)
        .options(selectinload(User.preferences))
        .join(UserPreference, UserPreference.user_id == User.id)
        .where(
            UserPreference.email_ingest_token == needle,
            User.is_active.is_(True),
            User.deleted_at.is_(None),
        )
    )


async def ingest_inbound_mail(
    db: AsyncSession,
    mail: InboundMail,
    *,
    ip: str | None = None,
) -> dict:
    token, plus, _domain = parse_ingest_recipient(mail.recipient)
    if not token:
        return {"accepted": False, "reason": "NO_MAILBOX", "documents": [], "process_ids": []}
    user = await user_for_ingest_token(db, token)
    if not user:
        log.info("ingest_unknown_mailbox")
        return {"accepted": False, "reason": "UNKNOWN_MAILBOX", "documents": [], "process_ids": []}

    rows = (await db.scalars(select(Collection).where(Collection.user_id == user.id))).all()
    matched = match_collection_for_ingest(list(rows), subject=mail.subject, plus_tag=plus)
    target_id = matched.id if matched else None
    folder = (matched.name if matched else None) or "Default"

    uploaded: list[dict] = []
    process_ids: list[str] = []
    skipped = 0
    kept = []
    for att in mail.attachments:
        if len(kept) >= MAX_ATTACHMENTS:
            skipped += 1
            continue
        if keep_attachment(att):
            kept.append(att)
        else:
            skipped += 1

    for att in kept:
        try:
            doc, duplicate = await create_upload(
                db,
                user.id,
                filename=att.filename or "email-attachment",
                data=att.data,
                title=None,
            )
            placed = await place_uploaded_document(db, user.id, doc.id, target_id)
            await db.commit()
            if not duplicate:
                process_ids.append(doc.id)
            uploaded.append(
                {
                    **serialize_document(doc),
                    "duplicate": duplicate,
                    "collection_id": placed.id,
                    "collection_name": placed.name,
                }
            )
            folder = placed.name or folder
        except AppError as exc:
            log.info("ingest_skip_attachment", code=exc.code)
            skipped += 1

    if uploaded:
        names = ", ".join(item.get("title") or "file" for item in uploaded[:4])
        body = f"{len(uploaded)} file(s) saved to {folder}: {names}"
        await log_security_event(db, "email_ingest", user_id=user.id, ip=ip, detail=folder)
        await notify(
            db,
            user,
            kind="email_ingest",
            title="Files arrived by email",
            body=body,
            link="/documents",
        )

    return {
        "accepted": True,
        "reason": None,
        "collection": folder,
        "matched_subject": bool(matched),
        "skipped": skipped,
        "documents": uploaded,
        "process_ids": process_ids,
    }
