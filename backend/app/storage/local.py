"""Hostinger VPS local disk storage. Originals never leave this filesystem via the web server."""

from __future__ import annotations

import hashlib
import os
from pathlib import Path

import aiofiles

from app.config import get_settings
from app.exceptions import AppError

settings = get_settings()

ALLOWED_EXTENSIONS = {
    ".pdf",
    ".jpg",
    ".jpeg",
    ".png",
    ".webp",
    ".heic",
    ".docx",
    ".xlsx",
    ".txt",
}

ALLOWED_MIME = {
    "application/pdf",
    "image/jpeg",
    "image/png",
    "image/webp",
    "image/heic",
    "image/heif",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "text/plain",
}

MAGIC_PREFIXES: list[tuple[bytes, str, str]] = [
    (b"%PDF", "application/pdf", ".pdf"),
    (b"\xff\xd8\xff", "image/jpeg", ".jpg"),
    (b"\x89PNG\r\n\x1a\n", "image/png", ".png"),
    (b"RIFF", "image/webp", ".webp"),
    (b"PK\x03\x04", "application/zip", ".docx"),
]


def storage_root() -> Path:
    root = Path(settings.storage_root).resolve()
    root.mkdir(parents=True, exist_ok=True)
    return root


def user_dir(user_id: str) -> Path:
    path = storage_root() / "users" / user_id
    for sub in ("documents", "thumbnails", "previews", "encrypted", "temp"):
        (path / sub).mkdir(parents=True, exist_ok=True)
    return path


def document_path(user_id: str, document_id: str, extension: str) -> Path:
    ext = extension if extension.startswith(".") else f".{extension}"
    return user_dir(user_id) / "documents" / f"{document_id}{ext}"


def thumbnail_path(user_id: str, document_id: str) -> Path:
    return user_dir(user_id) / "thumbnails" / f"{document_id}.jpg"


def preview_path(user_id: str, document_id: str, page: int = 1) -> Path:
    return user_dir(user_id) / "previews" / f"{document_id}-p{page}.jpg"


def relative_key(path: Path) -> str:
    return str(path.resolve().relative_to(storage_root()))


def resolve_key(storage_key: str) -> Path:
    root = storage_root()
    path = (root / storage_key).resolve()
    if not str(path).startswith(str(root)):
        raise AppError("PATH_TRAVERSAL", "Invalid storage path", 400)
    return path


def detect_type(data: bytes, filename: str) -> tuple[str, str]:
    name = filename.lower()
    ext = Path(name).suffix
    mime = "application/octet-stream"
    for prefix, detected_mime, detected_ext in MAGIC_PREFIXES:
        if data.startswith(prefix):
            mime = detected_mime
            if detected_ext == ".docx" and name.endswith(".xlsx"):
                ext = ".xlsx"
                mime = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            elif detected_ext == ".docx" and name.endswith(".docx"):
                mime = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                ext = ".docx"
            elif detected_ext != ".docx":
                ext = detected_ext if ext not in {".jpeg", ".jpg"} else ext
            break
    if data[:8] == b"ftypheic" or b"ftypheic" in data[:16] or b"ftypheif" in data[:16]:
        mime = "image/heic"
        ext = ".heic"
    if ext == ".txt" or (not data[:8].isascii() is False and name.endswith(".txt")):
        if name.endswith(".txt"):
            mime = "text/plain"
            ext = ".txt"
    if ext not in ALLOWED_EXTENSIONS:
        raise AppError("UNSUPPORTED_TYPE", f"File type {ext or 'unknown'} is not supported", 415)
    if mime not in ALLOWED_MIME and ext not in {".docx", ".xlsx", ".heic"}:
        if ext == ".txt":
            mime = "text/plain"
        else:
            raise AppError("UNSUPPORTED_TYPE", "File MIME type is not allowed", 415)
    return mime, ext


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


async def write_bytes(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".part")
    async with aiofiles.open(tmp, "wb") as handle:
        await handle.write(data)
    os.replace(tmp, path)


async def read_bytes(path: Path) -> bytes:
    async with aiofiles.open(path, "rb") as handle:
        return await handle.read()


def delete_file(path: Path) -> None:
    if path.exists():
        path.unlink()
