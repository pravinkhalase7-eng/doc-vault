"""Reminders and appointments created from Ask My Vault chat."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ai import AIProposal
from app.models.collection import Reminder
from app.models.user import User
from app.ai.vault_actions import parse_vault_intent
from app.reminders.service import (
    attach_phone,
    cancel_reminder,
    create_call_reminder,
    latest_active_reminder,
    list_active_reminders,
    reminder_view,
)
from app.utils.datetime_parse import extract_offset_minutes, format_local, parse_natural_datetime
from app.utils.phone import looks_like_phone, normalize_phone

SCHEDULE_KINDS = ("schedule_ask_title", "schedule_ask_time", "schedule_ask_phone")
CANCEL_PHRASES = {
    "no",
    "n",
    "cancel",
    "cancelled",
    "canceled",
    "nevermind",
    "never mind",
    "stop",
    "no thanks",
}


@dataclass
class ScheduleIntent:
    kind: str
    title: str | None = None


def infer_title(text: str) -> str:
    cleaned = re.sub(r"^\s*(hey\s+)?(docvault|vault)[,:]?\s*", "", text or "", flags=re.I).strip()
    patterns = [
        r"(?:to|about)\s+(.+)$",
        r"remind me\s+(?:that\s+)?(.+)$",
    ]
    for pat in patterns:
        match = re.search(pat, cleaned, re.I)
        if match:
            title = match.group(1).strip().rstrip(".")
            title = re.sub(
                r"^(tomorrow|today|tonight|at\s+\d.*|in\s+\d+\s+\w+)\s+",
                "",
                title,
                flags=re.I,
            )
            title = re.sub(r"\s+at\s+\d{1,2}(:\d{2})?\s*(am|pm)?\b.*$", "", title, flags=re.I)
            if title and not re.fullmatch(r"(tomorrow|today|tonight|please)", title, re.I):
                return title[:1].upper() + title[1:]
    if "call" in cleaned.lower():
        match = re.search(r"call\s+([A-Za-z][\w\s]{1,40})", cleaned, re.I)
        if match:
            name = match.group(1).strip().title()
            if name.lower() not in {"me", "us", "them"}:
                return f"Call {name}"
    return ""


def appointment_title(text: str) -> str:
    lower = text.lower()
    if "doctor" in lower:
        return "Doctor Appointment"
    if "dentist" in lower:
        return "Dentist Appointment"
    if "meeting" in lower:
        return "Meeting"
    return "Appointment"


def parse_schedule_intent(message: str) -> ScheduleIntent:
    text = re.sub(r"\s+", " ", (message or "").strip())
    lowered = text.lower()
    if not lowered:
        return ScheduleIntent("none")
    if lowered in CANCEL_PHRASES:
        return ScheduleIntent("cancel")
    if re.search(r"\b(what reminders|list reminders|my reminders|do i have reminders)\b", lowered):
        return ScheduleIntent("list")
    if re.search(r"\b(cancel|remove|delete)\b.{0,40}\b(reminder|appointment|booking|call)\b", lowered) or re.search(
        r"\b(reminder|appointment|booking)\b.{0,24}\b(cancel|remove|delete)\b", lowered
    ):
        return ScheduleIntent("cancel_item")
    if re.search(r"\b(cancel it|cancel that|cancel the reminder|cancel the appointment)\b", lowered):
        return ScheduleIntent("cancel_item")
    if re.search(r"\b(appointment|doctor|dentist|meeting|clinic|hospital)\b", lowered):
        return ScheduleIntent("appointment", appointment_title(text))
    if re.search(r"\b(remind|reminder|call me)\b", lowered):
        return ScheduleIntent("reminder", infer_title(text) or None)
    return ScheduleIntent("none")


def _tz(user: User) -> str:
    return (user.preferences.timezone if user.preferences else None) or "Asia/Kolkata"


def _lang(user: User) -> str:
    prefs = user.preferences
    value = getattr(getattr(prefs, "language", None), "value", None) if prefs else None
    return value or "en"


def _proposal_view(proposal: AIProposal, summary: str) -> dict:
    return {
        "id": proposal.id,
        "kind": proposal.kind,
        "status": proposal.status,
        "summary": summary,
        "payload": proposal.payload or {},
    }


async def _latest_pending(db: AsyncSession, user_id: str) -> AIProposal | None:
    rows = (
        await db.scalars(
            select(AIProposal)
            .where(
                AIProposal.user_id == user_id,
                AIProposal.status == "pending",
                AIProposal.kind.in_(SCHEDULE_KINDS),
            )
            .order_by(AIProposal.created_at.desc())
        )
    ).all()
    return rows[0] if rows else None


async def _cancel_pending(db: AsyncSession, user_id: str) -> None:
    pending = await _latest_pending(db, user_id)
    if pending:
        pending.status = "rejected"
        await db.flush()


def _reply(answer: str, proposal: dict | None = None) -> dict:
    return {"answer": answer, "proposal": proposal}


async def handle_schedule_action(
    db: AsyncSession, user: User, message: str, conversation_id: str
) -> dict | None:
    pending = await _latest_pending(db, user.id)
    intent = parse_schedule_intent(message)

    if pending and intent.kind == "cancel":
        pending.status = "rejected"
        await db.flush()
        return _reply("Cancelled. I won't set that reminder.")

    if pending and pending.kind == "schedule_ask_phone":
        phone = normalize_phone(message)
        if phone:
            reminder_id = (pending.payload or {}).get("reminder_id")
            reminder = await db.get(Reminder, reminder_id) if reminder_id else None
            if reminder is None:
                reminder = await latest_active_reminder(db, user.id)
            if reminder is None or reminder.user_id != user.id:
                pending.status = "rejected"
                await db.flush()
                return _reply("I couldn't find that reminder. Try setting it again.")
            await attach_phone(db, user, reminder, phone)
            pending.status = "accepted"
            await db.flush()
            view = reminder_view(reminder)
            return _reply(
                f"Saved {view['phone_masked']}. I'll call you {view['when_label']} about {reminder.title}.",
                _proposal_view(pending, "Phone saved"),
            )
        if intent.kind == "none" and parse_vault_intent(message).kind == "none" and not looks_like_phone(message):
            return _reply("I need a mobile number to call you, e.g. 98765 43210.")
        pending.status = "rejected"
        await db.flush()

    if pending and pending.kind == "schedule_ask_title":
        title = infer_title(message) or message.strip()[:80]
        if len(title) < 2:
            return _reply("What should I remind you about?")
        payload = dict(pending.payload or {})
        payload["title"] = title[:1].upper() + title[1:]
        pending.status = "accepted"
        await db.flush()
        return await _finish_or_ask_time(
            db, user, conversation_id, payload.get("source_text") or message, payload, kind=payload.get("kind") or "reminder"
        )

    if pending and pending.kind == "schedule_ask_time":
        payload = dict(pending.payload or {})
        combined = f"{payload.get('source_text') or ''} {message}".strip()
        pending.status = "accepted"
        await db.flush()
        return await _finish_or_ask_time(
            db,
            user,
            conversation_id,
            combined,
            {**payload, "title": payload.get("title")},
            kind=payload.get("kind") or "reminder",
        )

    if intent.kind == "list":
        rows = await list_active_reminders(db, user.id)
        upcoming = [reminder_view(row) for row in rows if row.sent_at is None]
        if not upcoming:
            return _reply("You don't have any upcoming reminders.")
        lines = [f"{i + 1}. {item['title']} — {item['when_label']}" for i, item in enumerate(upcoming)]
        return _reply("Here are your reminders:\n\n" + "\n".join(lines))

    if intent.kind == "cancel_item":
        row = await latest_active_reminder(db, user.id)
        if not row:
            return _reply("I don't have a reminder to cancel.")
        await cancel_reminder(row)
        await db.flush()
        return _reply(f"Cancelled “{row.title}”. I won't call you for that.")

    if intent.kind in {"reminder", "appointment"}:
        await _cancel_pending(db, user.id)
        kind = "appointment" if intent.kind == "appointment" else "reminder"
        title = intent.title
        if kind == "reminder" and not title:
            proposal = AIProposal(
                user_id=user.id,
                kind="schedule_ask_title",
                payload={"kind": kind, "source_text": message},
                status="pending",
            )
            db.add(proposal)
            await db.flush()
            return _reply(
                "What would you like me to remind you about?",
                _proposal_view(proposal, "Waiting for reminder title"),
            )
        return await _finish_or_ask_time(
            db,
            user,
            conversation_id,
            message,
            {"title": title or appointment_title(message), "kind": kind, "source_text": message},
            kind=kind,
        )

    if looks_like_phone(message):
        row = await latest_active_reminder(db, user.id)
        extra = row.extra if row else {}
        if row and extra.get("needs_phone"):
            phone = normalize_phone(message)
            await attach_phone(db, user, row, phone or "")
            view = reminder_view(row)
            return _reply(f"Saved {view['phone_masked']}. I'll call you {view['when_label']} about {row.title}.")

    return None


async def _finish_or_ask_time(
    db: AsyncSession,
    user: User,
    conversation_id: str,
    source_text: str,
    payload: dict[str, Any],
    *,
    kind: str,
) -> dict:
    parsed = parse_natural_datetime(source_text, timezone_name=_tz(user))
    title = (payload.get("title") or infer_title(source_text) or appointment_title(source_text)).strip()
    if parsed is None or parsed.ambiguous:
        proposal = AIProposal(
            user_id=user.id,
            kind="schedule_ask_time",
            payload={**payload, "title": title, "kind": kind, "source_text": source_text, "conversation_id": conversation_id},
            status="pending",
        )
        db.add(proposal)
        await db.flush()
        prompt = "Sure. What time should I remind you?" if kind == "reminder" else "What time is the appointment?"
        return _reply(prompt, _proposal_view(proposal, "Waiting for a time"))

    offset = parsed.offset_minutes or extract_offset_minutes(source_text) or 0
    appointment_at = parsed.dt_utc if kind == "appointment" else None
    fire_at = parsed.dt_utc - timedelta(minutes=offset) if kind == "appointment" else parsed.dt_utc
    reminder = await create_call_reminder(
        db,
        user,
        title=title,
        fire_at=fire_at,
        kind=kind,
        timezone_name=_tz(user),
        appointment_at=appointment_at,
        language=_lang(user),
    )
    view = reminder_view(reminder)
    when = view["when_label"]
    if kind == "appointment" and offset:
        call_at = format_local(fire_at, _tz(user))
        answer = f"Done. I've added your {title.lower()} for {when}, and I'll call you at {call_at}."
    elif kind == "appointment":
        answer = f"Done. I've added your {title.lower()} for {when}, and I'll call you then."
    else:
        answer = f"Done. I'll remind you {when} to {title[0].lower() + title[1:] if title else 'do that'}."
    if view["needs_phone"]:
        proposal = AIProposal(
            user_id=user.id,
            kind="schedule_ask_phone",
            payload={"reminder_id": reminder.id, "kind": kind},
            status="pending",
        )
        db.add(proposal)
        await db.flush()
        return _reply(
            answer + " What's your Indian mobile number so I can call you?",
            _proposal_view(proposal, "Waiting for a phone number"),
        )
    settings_note = ""
    from app.config import get_settings

    if not get_settings().twilio_configured:
        settings_note = " Your number is saved. The server still needs a Twilio rebuild before I can place the call."
    return _reply(answer + settings_note)
