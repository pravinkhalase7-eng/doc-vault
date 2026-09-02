"""Outbound Twilio voice calls for due reminders."""

from __future__ import annotations

from app.config import get_settings
from app.logging import get_logger
from app.utils.phone import mask_phone

log = get_logger("twilio")

SAY_VOICE = {"en": ("Polly.Joanna", "en-IN"), "hi": ("Polly.Aditi", "hi-IN")}


def _xml_escape(text: str) -> str:
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&apos;")
    )


def reminder_twiml(spoken_text: str, language: str = "en") -> str:
    lang = "hi" if (language or "en").startswith("hi") else "en"
    voice, locale = SAY_VOICE[lang]
    body = _xml_escape(spoken_text)
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        f'<Response><Say voice="{voice}" language="{locale}">{body}</Say></Response>'
    )


def place_reminder_call(*, to: str, spoken_text: str, language: str = "en") -> str:
    settings = get_settings()
    if not settings.twilio_configured:
        raise RuntimeError("Twilio is not configured")
    from twilio.rest import Client

    client = Client(settings.twilio_account_sid, settings.twilio_auth_token)
    call = client.calls.create(
        to=to,
        from_=settings.twilio_phone_number,
        twiml=reminder_twiml(spoken_text, language),
    )
    sid = call.sid or ""
    log.info("voice_call_queued", to=mask_phone(to), sid=sid, status=call.status)
    return sid
