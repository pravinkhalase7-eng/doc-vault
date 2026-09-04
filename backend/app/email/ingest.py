"""Parse inbound mail and match a collection from the subject or plus-tag."""

from __future__ import annotations

import base64
import hashlib
import re
from dataclasses import dataclass, field
from email import policy
from email.parser import BytesParser
from email.utils import getaddresses
from secrets import compare_digest, token_hex

from app.config import get_settings
from app.exceptions import AppError
from app.storage.local import detect_type, sha256_bytes

FWD_PREFIX = re.compile(r"^(re|fw|fwd)\s*:\s*", re.I)
SKIP_NAMES = {
    "winmail.dat",
    "smime.p7s",
    "untitled attachment",
    "logo.png",
    "logo.jpg",
    "logo.gif",
    "image001.png",
    "image001.jpg",
}
SKIP_SUFFIXES = (".p7s", ".ics", ".vcf", ".eml")
MAX_ATTACHMENTS = 12


@dataclass
class InboundAttachment:
    filename: str
    data: bytes
    inline: bool = False
    mime: str = ""


@dataclass
class InboundMail:
    recipient: str
    sender: str
    subject: str
    attachments: list[InboundAttachment] = field(default_factory=list)
    message_id: str = ""


def generate_ingest_token() -> str:
    return "dv" + token_hex(6)


def collection_slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", (name or "").lower())


def normalize_subject(subject: str) -> str:
    text = (subject or "").strip()
    while True:
        nxt = FWD_PREFIX.sub("", text, count=1)
        if nxt == text:
            break
        text = nxt.strip()
    return text.strip()


def extract_addresses(value: str) -> list[str]:
    if not (value or "").strip():
        return []
    return [addr.strip().lower() for _name, addr in getaddresses([value]) if addr and "@" in addr]


def split_local_part(local: str) -> tuple[str, str | None]:
    raw = (local or "").strip().lower()
    if "+" in raw:
        token, plus = raw.split("+", 1)
        plus = plus.strip() or None
        return token, plus
    return raw, None


def parse_ingest_recipient(value: str) -> tuple[str | None, str | None, str | None]:
    """Return (token, plus_tag, domain) for the first email in To/recipient."""
    for addr in extract_addresses(value) or [value.strip().lower()]:
        if "@" not in addr:
            continue
        local, domain = addr.rsplit("@", 1)
        token, plus = split_local_part(local)
        if token:
            return token, plus, domain
    return None, None, None


def sender_email(value: str) -> str | None:
    addrs = extract_addresses(value)
    return addrs[0] if addrs else None


def is_shared_inbox_recipient(recipient: str, shared_inbox: str) -> bool:
    shared = (shared_inbox or "").strip().lower()
    if not shared or "@" not in shared:
        return False
    shared_local, shared_domain = shared.rsplit("@", 1)
    shared_local = shared_local.split("+", 1)[0]
    for addr in extract_addresses(recipient) or [recipient.strip().lower()]:
        token, _plus, domain = parse_ingest_recipient(addr)
        if token == shared_local and (domain or "") == shared_domain:
            return True
    return False


def mail_fingerprint(mail: InboundMail) -> str:
    mid = (mail.message_id or "").strip()
    if mid:
        return hashlib.sha256(mid.encode("utf-8")).hexdigest()
    digest = hashlib.sha256()
    digest.update((mail.sender or "").encode("utf-8"))
    digest.update(b"\n")
    digest.update((mail.subject or "").encode("utf-8"))
    for att in mail.attachments:
        digest.update(b"\n")
        digest.update((att.filename or "").encode("utf-8"))
        digest.update(sha256_bytes(att.data).encode("utf-8"))
    return digest.hexdigest()


def ingest_secret_ok(provided: str | None, expected: str | None) -> bool:
    got = (provided or "").strip()
    want = (expected or "").strip()
    if not got or not want or len(got) != len(want):
        return False
    return compare_digest(got, want)


def match_collection_for_ingest(collections: list, *, subject: str, plus_tag: str | None = None):
    rows = list(collections or [])
    if plus_tag:
        needle = collection_slug(plus_tag)
        if needle:
            hits = [col for col in rows if collection_slug(getattr(col, "name", "") or "") == needle]
            if len(hits) == 1:
                return hits[0]
    hay = normalize_subject(subject).lower()
    if not hay:
        return None
    scored: list = []
    for col in rows:
        name = (getattr(col, "name", None) or "").strip()
        if len(name) < 2:
            continue
        pattern = r"(?<![a-z0-9])" + re.escape(name.lower()) + r"(?![a-z0-9])"
        if re.search(pattern, hay):
            scored.append(col)
    if not scored:
        return None
    scored.sort(key=lambda col: len((getattr(col, "name", None) or "").strip()), reverse=True)
    best_len = len((getattr(scored[0], "name", None) or "").strip())
    top = [col for col in scored if len((getattr(col, "name", None) or "").strip()) == best_len]
    if len(top) > 1:
        return None
    return scored[0]


def keep_attachment(att: InboundAttachment) -> bool:
    name = (att.filename or "attachment").strip() or "attachment"
    lower = name.lower()
    if lower in SKIP_NAMES or lower.endswith(SKIP_SUFFIXES):
        return False
    if not att.data or len(att.data) < 64:
        return False
    mime = (att.mime or "").lower()
    if att.inline and len(att.data) < 40_000 and mime.startswith("image/"):
        return False
    settings = get_settings()
    if len(att.data) > settings.max_upload_size:
        return False
    try:
        detect_type(att.data, name)
    except AppError:
        return False
    return True


def attachments_from_mime(raw: bytes) -> list[InboundAttachment]:
    if not raw:
        return []
    msg = BytesParser(policy=policy.default).parsebytes(raw)
    found: list[InboundAttachment] = []
    for part in msg.walk():
        if part.is_multipart():
            continue
        ctype = (part.get_content_type() or "").lower()
        disp = (part.get_content_disposition() or "").lower()
        filename = part.get_filename() or ""
        if disp in {"", "inline"} and ctype in {"text/plain", "text/html"} and not filename:
            continue
        payload = part.get_payload(decode=True) or b""
        found.append(
            InboundAttachment(
                filename=filename or "attachment",
                data=payload,
                inline=disp == "inline",
                mime=ctype,
            )
        )
    return found


def mail_from_mime(raw: bytes, *, fallback_recipient: str = "") -> InboundMail:
    msg = BytesParser(policy=policy.default).parsebytes(raw)
    to_value = msg.get("To") or msg.get("Delivered-To") or fallback_recipient
    return InboundMail(
        recipient=str(to_value or fallback_recipient),
        sender=str(msg.get("From") or ""),
        subject=str(msg.get("Subject") or ""),
        attachments=attachments_from_mime(raw),
        message_id=str(msg.get("Message-ID") or ""),
    )


def _decode_maybe_b64(value: str) -> bytes:
    text = (value or "").strip()
    if not text:
        return b""
    pad = "=" * ((4 - len(text) % 4) % 4)
    try:
        return base64.b64decode(text + pad)
    except Exception:
        return text.encode("utf-8", errors="replace")


def mail_from_json(payload: dict) -> InboundMail:
    raw = payload.get("raw") or payload.get("message")
    files = payload.get("attachments") or []
    if isinstance(raw, (bytes, bytearray)) and raw and not files:
        return mail_from_mime(bytes(raw), fallback_recipient=str(payload.get("recipient") or payload.get("to") or ""))
    if isinstance(raw, str) and raw.strip() and not files:
        return mail_from_mime(_decode_maybe_b64(raw), fallback_recipient=str(payload.get("recipient") or payload.get("to") or ""))
    attachments: list[InboundAttachment] = []
    if isinstance(files, list):
        for item in files:
            if not isinstance(item, dict):
                continue
            content = item.get("content") or item.get("content_base64") or item.get("Content") or ""
            if isinstance(content, str):
                data = _decode_maybe_b64(content)
            elif isinstance(content, (bytes, bytearray)):
                data = bytes(content)
            else:
                continue
            attachments.append(
                InboundAttachment(
                    filename=str(item.get("filename") or item.get("Name") or "attachment"),
                    data=data,
                    inline=str(item.get("disposition") or item.get("Disposition") or "").lower() == "inline",
                    mime=str(item.get("content_type") or item.get("ContentType") or ""),
                )
            )
    return InboundMail(
        recipient=str(payload.get("recipient") or payload.get("to") or payload.get("To") or ""),
        sender=str(payload.get("sender") or payload.get("from") or payload.get("From") or ""),
        subject=str(payload.get("subject") or payload.get("Subject") or ""),
        attachments=attachments,
        message_id=str(payload.get("message_id") or payload.get("MessageID") or ""),
    )


def ingest_address_for(token: str, domain: str | None = None) -> str:
    host = (domain or get_settings().inbound_mail_domain).strip().lower().lstrip("@")
    return f"{token}@{host}"
