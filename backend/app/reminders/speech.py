"""Spoken reminder copy for outbound Twilio calls."""

from __future__ import annotations

from datetime import datetime

from app.models.collection import Reminder
from app.utils.datetime_parse import format_local, to_utc


def _when(reminder: Reminder):
    extra = reminder.extra or {}
    raw = extra.get("appointment_at") or reminder.fire_at
    if isinstance(raw, str):
        try:
            return to_utc(datetime.fromisoformat(raw.replace("Z", "+00:00")))
        except ValueError:
            return reminder.fire_at
    return raw


def reminder_speech(reminder: Reminder, *, language: str = "en") -> str:
    extra = reminder.extra or {}
    tz = extra.get("timezone") or "Asia/Kolkata"
    try:
        time_label = format_local(_when(reminder), tz, with_date=False)
    except Exception:
        time_label = extra.get("when_label") or "the scheduled time"
    title = reminder.title or "your reminder"
    kind = extra.get("kind") or "reminder"
    if (language or "en").startswith("hi"):
        if kind == "appointment":
            body = f"मैं आपकी अपॉइंटमेंट के बारे में कॉल कर रही हूँ, {title}, {time_label}।"
        else:
            body = f"आपकी याद दिलाने की कॉल है: {title}, {time_label}।"
        return f"नमस्ते, यह DocVault है। {body} कृपया इसे न भूलें।"
    if kind == "appointment":
        body = f"I'm calling about your appointment, {title}, at {time_label}."
    else:
        body = f"This is your reminder for {title} at {time_label}."
    return f"Hello, this is DocVault. {body} Please don't forget. Have a great day."
