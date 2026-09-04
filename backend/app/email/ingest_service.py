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
    is_shared_inbox_recipient,
    keep_attachment,
    mail_fingerprint,
    match_collection_for_ingest,
    parse_ingest_recipient,
    sender_email,
)
from app.email.notification_service import notify
from app.exceptions import AppError
from app.logging import get_logger
from app.models.collection import Collection
from app.models.system import InboundMailReceipt
from app.models.user import User, UserPreference

log = get_logger("email.ingest")
settings = get_settings()


def _empty_result(reason: str) -> dict:
    return {"accepted": False, "reason": reason, "documents": [], "process_ids": []}


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
    shared = settings.shared_inbox_address
    return {
        "address": ingest_address_for(token),
        "domain": settings.inbound_mail_domain,
        "receiving": settings.inbound_webhook_enabled,
        "shared_inbox": shared,
        "shared_inbox_enabled": settings.imap_configured,
        "login_email": user.email,
        "hint": (
            f"Send a PDF from {user.email} to {shared}. "
            "Put the collection name in the subject — Insurance, Bills — or it goes to Default."
        ),
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


async def user_for_sender_email(db: AsyncSession, sender: str) -> User | None:
    email = sender_email(sender)
    if not email:
        return None
    if email == settings.shared_inbox_address:
        return None
    if email == (settings.guest_email or "").strip().lower():
        return None
    return await db.scalar(
        select(User)
        .options(selectinload(User.preferences))
        .where(User.email == email, User.is_active.is_(True), User.deleted_at.is_(None))
    )


async def _already_ingested(db: AsyncSession, fingerprint: str) -> bool:
    found = await db.scalar(select(InboundMailReceipt.id).where(InboundMailReceipt.fingerprint == fingerprint))
    return bool(found)


async def _record_receipt(
    db: AsyncSession,
    *,
    fingerprint: str,
    sender: str,
    user_id: str | None,
    status: str,
    detail: str | None = None,
) -> None:
    existing = await db.scalar(select(InboundMailReceipt).where(InboundMailReceipt.fingerprint == fingerprint))
    if existing:
        return
    db.add(
        InboundMailReceipt(
            fingerprint=fingerprint,
            sender=(sender or "")[:320],
            user_id=user_id,
            status=status,
            detail=(detail or "")[:200] or None,
        )
    )
    await db.commit()


async def ingest_mail_for_user(
    db: AsyncSession,
    user: User,
    mail: InboundMail,
    *,
    plus_tag: str | None = None,
    ip: str | None = None,
) -> dict:
    rows = (await db.scalars(select(Collection).where(Collection.user_id == user.id))).all()
    matched = match_collection_for_ingest(list(rows), subject=mail.subject, plus_tag=plus_tag)
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


async def ingest_inbound_mail(
    db: AsyncSession,
    mail: InboundMail,
    *,
    ip: str | None = None,
) -> dict:
    fingerprint = mail_fingerprint(mail)
    if await _already_ingested(db, fingerprint):
        return {**_empty_result("DUPLICATE"), "accepted": True, "reason": "DUPLICATE"}

    token, plus, _domain = parse_ingest_recipient(mail.recipient)
    shared = settings.shared_inbox_address
    if is_shared_inbox_recipient(mail.recipient, shared):
        user = await user_for_sender_email(db, mail.sender)
        if not user:
            log.info("ingest_unknown_sender")
            await _record_receipt(
                db,
                fingerprint=fingerprint,
                sender=sender_email(mail.sender) or mail.sender,
                user_id=None,
                status="ignored",
                detail="UNKNOWN_SENDER",
            )
            return _empty_result("UNKNOWN_SENDER")
        result = await ingest_mail_for_user(db, user, mail, plus_tag=plus, ip=ip)
        await _record_receipt(
            db,
            fingerprint=fingerprint,
            sender=user.email,
            user_id=user.id,
            status="accepted" if result.get("documents") else "empty",
            detail=result.get("collection"),
        )
        return result

    if not token:
        await _record_receipt(
            db,
            fingerprint=fingerprint,
            sender=sender_email(mail.sender) or "",
            user_id=None,
            status="ignored",
            detail="NO_MAILBOX",
        )
        return _empty_result("NO_MAILBOX")
    user = await user_for_ingest_token(db, token)
    if not user:
        log.info("ingest_unknown_mailbox")
        await _record_receipt(
            db,
            fingerprint=fingerprint,
            sender=sender_email(mail.sender) or "",
            user_id=None,
            status="ignored",
            detail="UNKNOWN_MAILBOX",
        )
        return _empty_result("UNKNOWN_MAILBOX")

    result = await ingest_mail_for_user(db, user, mail, plus_tag=plus, ip=ip)
    await _record_receipt(
        db,
        fingerprint=fingerprint,
        sender=user.email,
        user_id=user.id,
        status="accepted" if result.get("documents") else "empty",
        detail=result.get("collection"),
    )
    return result
