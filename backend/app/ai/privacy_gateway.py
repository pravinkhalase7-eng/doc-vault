"""Every Gemini request must pass through this gateway. Originals stay on disk."""

from __future__ import annotations

import re

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.exceptions import PrivacyRejectedError
from app.logging import get_logger
from app.models.ai import AIAuditLog
from app.models.document import Document
from app.models.enums import AIOperation, AIPrivacyMode, HIGHLY_SENSITIVE_TYPES, SensitivityLevel
from app.models.user import User

log = get_logger("privacy")
settings = get_settings()

PII_PATTERNS = [
    (re.compile(r"\b\d{4}\s?\d{4}\s?\d{4}\b"), "possible_aadhaar"),
    (re.compile(r"\b[A-Z]{5}\d{4}[A-Z]\b"), "possible_pan"),
    (re.compile(r"\b(?:\d[ -]*?){13,19}\b"), "possible_card"),
]


def detect_pii_labels(text: str) -> list[str]:
    labels = []
    for pattern, label in PII_PATTERNS:
        if pattern.search(text or ""):
            labels.append(label)
    return labels


def minimize_text(text: str, max_chars: int = 1200) -> str:
    if not text:
        return ""
    cleaned = text
    for pattern, _ in PII_PATTERNS:
        cleaned = pattern.sub("[redacted]", cleaned)
    return cleaned[:max_chars]


async def check_ai_request(
    db: AsyncSession,
    user: User,
    operation: AIOperation,
    documents: list[Document],
    *,
    external_ai: bool,
    raw_document: bool = False,
) -> dict:
    prefs = user.preferences
    mode = prefs.ai_privacy_mode if prefs else AIPrivacyMode.PRIVATE
    allow_external = bool(prefs and prefs.external_ai_enabled and settings.gemini_configured)
    allow_highly = bool(prefs and prefs.allow_highly_sensitive_external)

    blocked: list[str] = []
    allowed: list[Document] = []
    for doc in documents:
        if doc.exclude_from_ai:
            blocked.append(f"{doc.title}: excluded from AI")
            continue
        if doc.user_id != user.id:
            blocked.append(f"{doc.title}: not owned by requester")
            continue
        if doc.trashed_at or doc.deleted_at:
            continue
        if external_ai and doc.sensitivity == SensitivityLevel.HIGHLY_SENSITIVE and not allow_highly:
            blocked.append(f"{doc.title}: highly sensitive — local processing only")
            continue
        slug = (doc.ai_classification or "").lower().replace(" ", "_")
        if external_ai and slug in HIGHLY_SENSITIVE_TYPES and not allow_highly:
            blocked.append(f"{doc.title}: protected identity/financial/medical type")
            continue
        allowed.append(doc)

    if raw_document:
        raise PrivacyRejectedError("Original documents are never sent to external AI.")

    if external_ai:
        if mode == AIPrivacyMode.PRIVATE:
            raise PrivacyRejectedError("Cloud AI is disabled. Enable it in Privacy Center to use Gemini.")
        if not allow_external:
            raise PrivacyRejectedError("External AI is turned off for this vault.")
        if not settings.gemini_configured:
            raise PrivacyRejectedError("Gemini is not configured on the server.")

    decision = {
        "allowed_document_ids": [d.id for d in allowed],
        "blocked": blocked,
        "external_ai": external_ai,
        "operation": operation.value,
        "raw_document_sent": False,
        "mode": mode.value if hasattr(mode, "value") else str(mode),
    }
    db.add(
        AIAuditLog(
            user_id=user.id,
            operation=operation,
            documents_accessed=[d.id for d in allowed],
            model=settings.gemini_model if external_ai else "local",
            external_ai=external_ai,
            success=True,
            fields_used=["title", "type", "expiry_date", "metadata"],
            raw_document_sent=False,
            privacy_decision="allow" if allowed or not documents else "filtered",
            extra={"blocked": blocked},
        )
    )
    return decision
