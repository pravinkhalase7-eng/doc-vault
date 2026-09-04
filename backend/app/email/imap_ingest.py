"""Poll a shared Hostinger inbox (support@doxstation.com) over IMAP."""

from __future__ import annotations

import imaplib
import socket
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.email.ingest import mail_from_mime
from app.email.ingest_service import ingest_inbound_mail
from app.logging import get_logger

log = get_logger("email.imap")
settings = get_settings()
MAX_PER_POLL = 20


@dataclass
class FetchedMail:
    uid: bytes
    raw: bytes


def _connect() -> imaplib.IMAP4_SSL:
    host = (settings.imap_host or "").strip()
    port = int(settings.imap_port or 993)
    timeout = socket.getdefaulttimeout()
    socket.setdefaulttimeout(30)
    try:
        client = imaplib.IMAP4_SSL(host, port)
        client.login(settings.imap_user, settings.imap_pass)
        return client
    finally:
        socket.setdefaulttimeout(timeout)


def fetch_unseen() -> list[FetchedMail]:
    if not settings.imap_configured:
        return []
    folder = (settings.imap_folder or "INBOX").strip() or "INBOX"
    client = _connect()
    found: list[FetchedMail] = []
    try:
        typ, _ = client.select(folder)
        if typ != "OK":
            log.warning("imap_select_failed", folder=folder)
            return []
        typ, data = client.uid("search", None, "UNSEEN")
        if typ != "OK" or not data or not data[0]:
            return []
        for uid in data[0].split()[:MAX_PER_POLL]:
            typ, msg_data = client.uid("fetch", uid, "(RFC822)")
            if typ != "OK" or not msg_data:
                continue
            raw = None
            for part in msg_data:
                if isinstance(part, tuple) and len(part) > 1 and isinstance(part[1], bytes):
                    raw = part[1]
                    break
            if raw:
                found.append(FetchedMail(uid=uid, raw=raw))
        return found
    finally:
        try:
            client.logout()
        except Exception:
            pass


def mark_seen(uids: list[bytes]) -> None:
    if not uids or not settings.imap_configured:
        return
    folder = (settings.imap_folder or "INBOX").strip() or "INBOX"
    client = _connect()
    try:
        client.select(folder)
        for uid in uids:
            client.uid("store", uid, "+FLAGS", r"(\Seen)")
    finally:
        try:
            client.logout()
        except Exception:
            pass


async def poll_shared_inbox(db: AsyncSession) -> dict:
    if not settings.imap_configured:
        return {"skipped": True, "reason": "IMAP_DISABLED", "processed": 0}
    items = fetch_unseen()
    seen: list[bytes] = []
    processed = 0
    ignored = 0
    process_ids: list[str] = []
    for item in items:
        try:
            mail = mail_from_mime(item.raw, fallback_recipient=settings.shared_inbox_address)
            if not mail.recipient:
                mail.recipient = settings.shared_inbox_address
            result = await ingest_inbound_mail(db, mail)
            process_ids.extend(result.pop("process_ids", []) or [])
            if result.get("accepted") and result.get("documents"):
                processed += 1
            else:
                ignored += 1
            seen.append(item.uid)
        except Exception:
            log.exception("imap_message_failed")
    if seen:
        mark_seen(seen)
    return {
        "skipped": False,
        "fetched": len(items),
        "processed": processed,
        "ignored": ignored,
        "seen": len(seen),
        "process_ids": process_ids,
    }
