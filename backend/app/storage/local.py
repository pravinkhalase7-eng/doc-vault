"""Hostinger VPS local disk storage. Originals never leave this filesystem via the web server."""

from __future__ import annotations

import hashlib
import os
from pathlib import Path

import aiofiles

from app.config import get_settings
from app.exceptions import AppError

settings = get_settings()

EXT_TO_MIME = {
    ".pdf": "application/pdf",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".webp": "image/webp",
    ".gif": "image/gif",
    ".bmp": "image/bmp",
    ".tif": "image/tiff",
    ".tiff": "image/tiff",
    ".heic": "image/heic",
    ".heif": "image/heif",
    ".avif": "image/avif",
    ".txt": "text/plain",
    ".csv": "text/csv",
    ".rtf": "application/rtf",
    ".doc": "application/msword",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".xls": "application/vnd.ms-excel",
    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ".ppt": "application/vnd.ms-powerpoint",
    ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    ".odt": "application/vnd.oasis.opendocument.text",
}

ALLOWED_EXTENSIONS = frozenset(EXT_TO_MIME)
ALLOWED_MIME = frozenset(EXT_TO_MIME.values()) | {"image/heif"}

OFFICE_ZIP_EXT = {
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    ".odt": "application/vnd.oasis.opendocument.text",
}

OLE_EXT = {
    ".doc": "application/msword",
    ".xls": "application/vnd.ms-excel",
    ".ppt": "application/vnd.ms-powerpoint",
}

HEIF_BRANDS = (b"heic", b"heif", b"heix", b"heim", b"heis", b"hevc", b"hevx", b"mif1", b"msf1")


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


def _ftyp_brands(data: bytes) -> bytes:
    if len(data) < 12 or data[4:8] != b"ftyp":
        return b""
    size = int.from_bytes(data[:4], "big")
    end = size if 16 <= size <= 256 else min(64, len(data))
    return data[8:min(end, len(data))]


def _sniff(data: bytes, name: str) -> tuple[str | None, str | None]:
    if data.startswith(b"%PDF"):
        return "application/pdf", ".pdf"
    if data.startswith(b"\xff\xd8\xff"):
        return "image/jpeg", ".jpg" if not name.endswith(".jpeg") else ".jpeg"
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png", ".png"
    if data.startswith(b"RIFF") and data[8:12] == b"WEBP":
        return "image/webp", ".webp"
    if data.startswith(b"GIF87a") or data.startswith(b"GIF89a"):
        return "image/gif", ".gif"
    if data.startswith(b"BM"):
        return "image/bmp", ".bmp"
    if data.startswith(b"II*\x00") or data.startswith(b"MM\x00*"):
        return "image/tiff", ".tiff"
    brands = _ftyp_brands(data)
    if brands:
        if b"avif" in brands or b"avis" in brands:
            return "image/avif", ".avif"
        if any(brand in brands for brand in HEIF_BRANDS):
            ext = ".heif" if name.endswith(".heif") else ".heic"
            mime = "image/heif" if ext == ".heif" else "image/heic"
            return mime, ext
    if data.startswith(b"PK\x03\x04"):
        for ext, mime in OFFICE_ZIP_EXT.items():
            if name.endswith(ext):
                return mime, ext
        return None, None
    if data.startswith(b"\xd0\xcf\x11\xe0"):
        for ext, mime in OLE_EXT.items():
            if name.endswith(ext):
                return mime, ext
        if name.endswith(".doc"):
            return OLE_EXT[".doc"], ".doc"
        return OLE_EXT[".doc"], ".doc"
    return None, None


def detect_type(data: bytes, filename: str) -> tuple[str, str]:
    name = (filename or "upload").lower().strip()
    ext = Path(name).suffix
    sniffed_mime, sniffed_ext = _sniff(data, name)
    if sniffed_mime and sniffed_ext:
        mime, ext = sniffed_mime, sniffed_ext
    elif ext in EXT_TO_MIME:
        mime = EXT_TO_MIME[ext]
    else:
        raise AppError("UNSUPPORTED_TYPE", f"File type {ext or 'unknown'} is not supported", 415)
    if ext not in ALLOWED_EXTENSIONS or mime not in ALLOWED_MIME:
        raise AppError("UNSUPPORTED_TYPE", f"File type {ext or 'unknown'} is not supported", 415)
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
