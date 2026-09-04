"""Unauthenticated inbound-mail webhook. Secret is checked in the handler."""

from fastapi import APIRouter, BackgroundTasks, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database import get_db
from app.documents.processing import enqueue_document_processing
from app.email.ingest import ingest_secret_ok, mail_from_json
from app.email.ingest_service import ingest_inbound_mail
from app.exceptions import AppError, UnauthorizedError

router = APIRouter(prefix="/ingest", tags=["ingest"])
settings = get_settings()


def ok(data):
    return {"success": True, "data": data}


def _provided_secret(request: Request) -> str:
    header = request.headers.get("x-docvault-ingest-secret") or ""
    if header.strip():
        return header.strip()
    auth = request.headers.get("authorization") or ""
    if auth.lower().startswith("bearer "):
        return auth[7:].strip()
    return (request.query_params.get("secret") or "").strip()


async def _mail_from_request(request: Request):
    ctype = (request.headers.get("content-type") or "").lower()
    if "application/json" in ctype:
        payload = await request.json()
        if not isinstance(payload, dict):
            raise AppError("INVALID_MAIL", "Expected a JSON object", 400)
        return mail_from_json(payload)

    form = await request.form()
    payload: dict = {}
    files = []
    mime_bytes = b""
    for key, value in form.multi_items():
        if hasattr(value, "read"):
            data = await value.read()
            filename = getattr(value, "filename", None) or key
            if key.lower() in {"body-mime", "message", "raw"}:
                mime_bytes = data
            else:
                files.append(
                    {
                        "filename": filename,
                        "content": data,
                        "content_type": getattr(value, "content_type", None) or "",
                    }
                )
        else:
            payload[key] = str(value)
    if files:
        payload["attachments"] = files
    elif mime_bytes:
        payload["raw"] = mime_bytes
        payload.setdefault("recipient", payload.get("recipient") or payload.get("to") or "")
        from app.email.ingest import mail_from_mime

        mail = mail_from_mime(mime_bytes, fallback_recipient=str(payload.get("recipient") or payload.get("to") or ""))
        if payload.get("subject"):
            mail.subject = str(payload.get("subject"))
        if payload.get("recipient") or payload.get("to"):
            mail.recipient = str(payload.get("recipient") or payload.get("to"))
        if payload.get("sender") or payload.get("from"):
            mail.sender = str(payload.get("sender") or payload.get("from"))
        return mail
    if "to" in payload and "recipient" not in payload:
        payload["recipient"] = payload["to"]
    if "from" in payload and "sender" not in payload:
        payload["sender"] = payload["from"]
    return mail_from_json(payload)


@router.post("/email")
async def inbound_email(
    request: Request,
    background: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    if not settings.inbound_webhook_enabled:
        raise AppError("INGEST_DISABLED", "Inbound email is not configured on this server", 503)
    if not ingest_secret_ok(_provided_secret(request), settings.inbound_webhook_secret):
        raise UnauthorizedError("INGEST_UNAUTHORIZED", "Invalid ingest secret")
    mail = await _mail_from_request(request)
    ip = request.client.host if request.client else None
    result = await ingest_inbound_mail(db, mail, ip=ip)
    for doc_id in result.pop("process_ids", []) or []:
        background.add_task(enqueue_document_processing, doc_id)
    return ok(result)


@router.post("/poll")
async def poll_shared_mailbox(
    request: Request,
    background: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    if not ingest_secret_ok(_provided_secret(request), settings.inbound_webhook_secret):
        raise UnauthorizedError("INGEST_UNAUTHORIZED", "Invalid ingest secret")
    if not settings.imap_configured:
        raise AppError("IMAP_DISABLED", "Shared inbox IMAP is not configured", 503)
    from app.email.imap_ingest import poll_shared_inbox

    result = await poll_shared_inbox(db)
    for doc_id in result.pop("process_ids", []) or []:
        background.add_task(enqueue_document_processing, doc_id)
    return ok(result)
