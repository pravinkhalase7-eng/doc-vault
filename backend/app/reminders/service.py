"""Create, list, cancel, and enqueue phone reminders."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sqlalchemy.orm.attributes import flag_modified

from app.logging import get_logger
from app.models.collection import Reminder
from app.models.user import User
from app.push.service import alert_reminder
from app.reminders.speech import reminder_speech
from app.utils.datetime_parse import format_local, now_utc
from app.utils.phone import mask_phone, normalize_phone

log = get_logger("reminders")


def reminder_view(row: Reminder) -> dict[str, Any]:
    extra = row.extra or {}
    tz = extra.get("timezone") or "Asia/Kolkata"
    return {
        "id": row.id,
        "title": row.title,
        "document_id": row.document_id,
        "offset_days": row.offset_days,
        "fire_at": row.fire_at,
        "sent_at": row.sent_at,
        "channel": row.channel,
        "kind": extra.get("kind") or "reminder",
        "when_label": extra.get("when_label") or format_local(row.fire_at, tz),
        "appointment_at": extra.get("appointment_at"),
        "phone_masked": mask_phone(extra.get("phone_number")),
        "needs_phone": bool(extra.get("needs_phone")),
        "cancelled": bool(extra.get("cancelled")),
        "call_sid": extra.get("call_sid"),
    }


def _prefs_phone(user: User) -> str | None:
    prefs = user.preferences
    return normalize_phone(prefs.phone_number if prefs else None)


def _extra(row: Reminder) -> dict:
    data = dict(row.extra or {})
    row.extra = data
    flag_modified(row, "extra")
    return data


async def create_call_reminder(
    db: AsyncSession,
    user: User,
    *,
    title: str,
    fire_at: datetime,
    kind: str = "reminder",
    timezone_name: str = "Asia/Kolkata",
    appointment_at: datetime | None = None,
    phone_number: str | None = None,
    language: str = "en",
) -> Reminder:
    if fire_at.tzinfo is None:
        fire_at = fire_at.replace(tzinfo=UTC)
    if fire_at <= now_utc():
        fire_at = now_utc() + timedelta(seconds=15)
    phone = normalize_phone(phone_number) or _prefs_phone(user)
    extra: dict[str, Any] = {
        "kind": kind,
        "timezone": timezone_name,
        "when_label": format_local(appointment_at or fire_at, timezone_name),
        "language": language,
        "needs_phone": not bool(phone),
    }
    if appointment_at:
        extra["appointment_at"] = appointment_at.isoformat()
    if phone:
        extra["phone_number"] = phone
    reminder = Reminder(
        user_id=user.id,
        title=title.strip()[:300],
        offset_days=0,
        fire_at=fire_at,
        channel="phone",
        extra=extra,
    )
    db.add(reminder)
    await db.flush()
    if phone:
        enqueue_reminder_call(reminder.id, fire_at)
    return reminder


def enqueue_reminder_call(reminder_id: str, fire_at: datetime) -> None:
    try:
        from app.workers.tasks import fire_reminder_call

        fire_reminder_call.apply_async(args=[reminder_id], eta=fire_at)
    except Exception:
        log.warning("celery_enqueue_failed", reminder_id=reminder_id)


async def list_active_reminders(db: AsyncSession, user_id: str) -> list[Reminder]:
    rows = (
        await db.scalars(
            select(Reminder)
            .where(Reminder.user_id == user_id)
            .order_by(Reminder.fire_at.asc())
        )
    ).all()
    return [row for row in rows if not (row.extra or {}).get("cancelled")]


async def latest_active_reminder(db: AsyncSession, user_id: str) -> Reminder | None:
    rows = await list_active_reminders(db, user_id)
    open_rows = [row for row in rows if row.sent_at is None]
    return open_rows[-1] if open_rows else (rows[-1] if rows else None)


async def cancel_reminder(reminder: Reminder) -> Reminder:
    extra = _extra(reminder)
    extra["cancelled"] = True
    extra["needs_phone"] = False
    reminder.extra = extra
    return reminder


async def attach_phone(db: AsyncSession, user: User, reminder: Reminder, phone: str) -> Reminder:
    extra = _extra(reminder)
    extra["phone_number"] = phone
    extra["needs_phone"] = False
    extra.pop("call_error", None)
    reminder.extra = extra
    flag_modified(reminder, "extra")
    if user.preferences:
        user.preferences.phone_number = phone
    never_called = not extra.get("call_sid")
    if never_called and not extra.get("cancelled"):
        reminder.sent_at = None
        enqueue_reminder_call(reminder.id, reminder.fire_at)
    await db.flush()
    return reminder


async def due_call_reminders(db: AsyncSession, *, now: datetime | None = None) -> list[Reminder]:
    moment = now or now_utc()
    rows = (
        await db.scalars(
            select(Reminder).where(
                Reminder.channel == "phone",
                Reminder.sent_at.is_(None),
                Reminder.fire_at <= moment,
            )
        )
    ).all()
    due = []
    for row in rows:
        extra = row.extra or {}
        if extra.get("cancelled"):
            continue
        if extra.get("needs_phone") and not extra.get("phone_number"):
            continue
        due.append(row)
    return due


async def deliver_reminder_call(db: AsyncSession, reminder: Reminder) -> str:
    extra = _extra(reminder)
    if extra.get("cancelled"):
        return "cancelled"
    if reminder.sent_at or extra.get("call_sid"):
        return "already_sent"
    user = (
        await db.scalars(select(User).options(selectinload(User.preferences)).where(User.id == reminder.user_id))
    ).first()
    if user and not extra.get("alerted"):
        when = extra.get("when_label") or format_local(reminder.fire_at, extra.get("timezone") or "Asia/Kolkata")
        await alert_reminder(
            db,
            user,
            title="DocVault reminder",
            body=f"{reminder.title} — {when}",
            reminder_id=reminder.id,
        )
        extra["alerted"] = True
        reminder.extra = extra
        flag_modified(reminder, "extra")
        await db.flush()
    phone = extra.get("phone_number")
    if not phone or extra.get("needs_phone"):
        extra["call_error"] = extra.get("call_error") or "No phone number on file"
        reminder.extra = extra
        flag_modified(reminder, "extra")
        return "no_phone"
    from app.config import get_settings as load_settings

    load_settings.cache_clear()
    settings = load_settings()
    language = extra.get("language") or "en"
    spoken = reminder_speech(reminder, language=language)
    extra["spoken_text"] = spoken
    if not settings.twilio_configured:
        extra["call_error"] = "Twilio is not configured"
        reminder.extra = extra
        flag_modified(reminder, "extra")
        log.warning("twilio_missing", reminder_id=reminder.id)
        return "not_configured"
    from app.reminders.twilio_voice import place_reminder_call

    try:
        sid = place_reminder_call(to=phone, spoken_text=spoken, language=language)
    except Exception as exc:
        extra["call_error"] = str(exc)
        reminder.extra = extra
        flag_modified(reminder, "extra")
        log.warning("voice_call_failed", reminder_id=reminder.id)
        return "failed"
    extra["call_sid"] = sid
    extra["call_error"] = None
    reminder.extra = extra
    flag_modified(reminder, "extra")
    reminder.sent_at = now_utc()
    return "called"
