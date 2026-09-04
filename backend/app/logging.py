"""Structured logging with redaction of secrets, tokens, and document content."""

import logging
import re
import sys
import uuid
from contextvars import ContextVar

import structlog

request_id_ctx: ContextVar[str] = ContextVar("request_id", default="")
user_id_ctx: ContextVar[str] = ContextVar("user_id", default="")

_SECRET_KEYS = {
    "password",
    "token",
    "refresh_token",
    "access_token",
    "secret",
    "api_key",
    "authorization",
    "smtp_password",
    "jwt_secret",
    "encryption_key",
    "gemini_api_key",
    "twilio_auth_token",
    "twilio_account_sid",
    "vapid_private_key",
    "google_client_secret",
    "inbound_webhook_secret",
    "imap_password",
}

_REDACT = re.compile(r"(password|token|secret|api[_-]?key)\s*[:=]\s*\S+", re.I)


def _redact_value(key: str, value: object) -> object:
    if key.lower() in _SECRET_KEYS:
        return "[redacted]"
    if isinstance(value, str) and len(value) > 4000:
        return value[:200] + "…[truncated]"
    return value


def _redact_event(_logger: object, _method: str, event_dict: dict) -> dict:
    for key, value in list(event_dict.items()):
        event_dict[key] = _redact_value(str(key), value)
        if isinstance(value, str):
            event_dict[key] = _REDACT.sub(r"\1=[redacted]", value)
    event_dict.setdefault("request_id", request_id_ctx.get())
    user_id = user_id_ctx.get()
    if user_id:
        event_dict.setdefault("user_id", user_id)
    return event_dict


def configure_logging(debug: bool = False) -> None:
    timestamper = structlog.processors.TimeStamper(fmt="iso")
    processors: list = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        timestamper,
        _redact_event,
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.JSONRenderer(),
    ]
    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(logging.DEBUG if debug else logging.INFO),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(file=sys.stdout),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    return structlog.get_logger(name)


def new_request_id() -> str:
    rid = str(uuid.uuid4())
    request_id_ctx.set(rid)
    return rid
