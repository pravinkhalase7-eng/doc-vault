"""Web Push (VAPID) delivery for reminder alerts."""

from __future__ import annotations

import json

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.logging import get_logger
from app.models.notification import Notification
from app.models.enums import NotificationChannel
from app.models.push import PushSubscription
from app.models.user import User
from app.push.vapid import resolved_vapid_keys

log = get_logger("push")


def vapid_public_key() -> str:
    try:
        public, _private = resolved_vapid_keys()
        return public
    except Exception:
        return ""


def push_configured() -> bool:
    try:
        public, private = resolved_vapid_keys()
        return bool(public and private)
    except Exception:
        return False


async def upsert_subscription(
    db: AsyncSession,
    user: User,
    *,
    endpoint: str,
    p256dh: str,
    auth: str,
    user_agent: str | None = None,
) -> PushSubscription:
    row = (
        await db.scalars(select(PushSubscription).where(PushSubscription.endpoint == endpoint))
    ).first()
    if row:
        if row.user_id != user.id:
            row.user_id = user.id
        row.p256dh = p256dh
        row.auth = auth
        row.user_agent = user_agent
        return row
    row = PushSubscription(
        user_id=user.id,
        endpoint=endpoint,
        p256dh=p256dh,
        auth=auth,
        user_agent=user_agent,
    )
    db.add(row)
    await db.flush()
    return row


async def delete_subscription(db: AsyncSession, user: User, endpoint: str) -> None:
    row = (
        await db.scalars(
            select(PushSubscription).where(
                PushSubscription.user_id == user.id,
                PushSubscription.endpoint == endpoint,
            )
        )
    ).first()
    if row:
        await db.delete(row)


async def send_web_push(db: AsyncSession, user: User, *, title: str, body: str, url: str = "/notifications") -> int:
    if not push_configured():
        return 0
    prefs = user.preferences
    if prefs and prefs.notification_push is False:
        return 0
    rows = (
        await db.scalars(select(PushSubscription).where(PushSubscription.user_id == user.id))
    ).all()
    if not rows:
        return 0
    settings = get_settings()
    public, private = resolved_vapid_keys()
    sent = 0
    stale: list[PushSubscription] = []
    payload = json.dumps({"title": title, "body": body, "url": url})
    from pywebpush import WebPushException, webpush

    claims = {"sub": settings.vapid_mailto or "mailto:docvault@localhost"}
    for row in rows:
        try:
            webpush(
                subscription_info={
                    "endpoint": row.endpoint,
                    "keys": {"p256dh": row.p256dh, "auth": row.auth},
                },
                data=payload,
                vapid_private_key=private,
                vapid_claims=claims,
            )
            sent += 1
        except WebPushException as exc:
            status = getattr(getattr(exc, "response", None), "status_code", None)
            log.warning("web_push_failed", user_id=user.id, status=status)
            if status in {404, 410}:
                stale.append(row)
        except Exception:
            log.warning("web_push_failed", user_id=user.id)
    for row in stale:
        await db.delete(row)
    return sent


async def alert_reminder(db: AsyncSession, user: User, *, title: str, body: str) -> None:
    db.add(
        Notification(
            user_id=user.id,
            title=title,
            body=body,
            kind="reminder",
            channel=NotificationChannel.IN_APP,
            link="/notifications",
        )
    )
    await send_web_push(db, user, title=title, body=body, url="/notifications")
