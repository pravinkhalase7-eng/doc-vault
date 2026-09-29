"""Import files from a shared Google Drive folder into the vault."""

from __future__ import annotations

import re
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

import httpx

from app.config import get_settings
from app.exceptions import AppError
from app.storage.local import ALLOWED_EXTENSIONS, ALLOWED_MIME, EXT_TO_MIME

settings = get_settings()

DRIVE_API = "https://www.googleapis.com/drive/v3"
MAX_FILES = 40
MAX_DEPTH = 5
DRIVE_ID_RE = re.compile(r"^[a-zA-Z0-9_-]{10,128}$")

GOOGLE_EXPORT = {
    "application/vnd.google-apps.document": ("application/pdf", ".pdf"),
    "application/vnd.google-apps.spreadsheet": (
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        ".xlsx",
    ),
    "application/vnd.google-apps.presentation": (
        "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        ".pptx",
    ),
    "application/vnd.google-apps.drawing": ("application/pdf", ".pdf"),
}

SKIP_GOOGLE = {
    "application/vnd.google-apps.form",
    "application/vnd.google-apps.map",
    "application/vnd.google-apps.site",
    "application/vnd.google-apps.jam",
    "application/vnd.google-apps.script",
    "application/vnd.google-apps.folder",
}

MIME_TO_EXT = {mime: ext for ext, mime in EXT_TO_MIME.items()}
MIME_ALIASES = {
    "image/jpg": "image/jpeg",
    "image/pjpeg": "image/jpeg",
    "image/x-png": "image/png",
}
SNIFF_LATER = {"", "application/octet-stream", "binary/octet-stream", "application/x-download"}


def parse_drive_folder_id(value: str) -> str:
    """Return a Drive folder id from a sharing URL or a raw id."""
    raw = (value or "").strip()
    if not raw:
        raise AppError("DRIVE_URL", "Paste a Google Drive folder link", 400)
    if DRIVE_ID_RE.fullmatch(raw) and "/" not in raw and " " not in raw:
        return raw

    parsed = urlparse(raw)
    host = (parsed.hostname or "").lower()
    if host not in {"drive.google.com", "docs.google.com"}:
        raise AppError("DRIVE_URL", "Use a Google Drive folder link", 400)

    path = unquote(parsed.path or "")
    folder_match = re.search(r"/folders/([a-zA-Z0-9_-]{10,128})", path)
    if folder_match:
        return folder_match.group(1)

    query = parse_qs(parsed.query)
    for key in ("id", "folder", "folderId"):
        candidate = (query.get(key) or [""])[0].strip()
        if DRIVE_ID_RE.fullmatch(candidate):
            return candidate

    raise AppError("DRIVE_URL", "That link is not a Drive folder", 400)


def _drive_id(value: str) -> str:
    if not DRIVE_ID_RE.fullmatch(value or ""):
        raise AppError("DRIVE_URL", "Invalid Google Drive id", 400)
    return value


class DriveFile:
    def __init__(self, file_id: str, name: str, mime_type: str, size: int | None = None) -> None:
        self.id = file_id
        self.name = name
        self.mime_type = mime_type
        self.size = size


async def collect_drive_files(
    folder_id: str,
    *,
    access_token: str | None,
    api_key: str | None,
) -> tuple[list[DriveFile], list[dict[str, str]]]:
    skipped: list[dict[str, str]] = []
    files: list[DriveFile] = []
    headers = _auth_headers(access_token)
    params_base = _auth_params(api_key)
    timeout = httpx.Timeout(30.0, connect=10.0)
    async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
        await _walk_folder(
            client,
            folder_id,
            depth=0,
            files=files,
            skipped=skipped,
            headers=headers,
            params_base=params_base,
        )
    return files, skipped


async def download_drive_file(
    item: DriveFile,
    *,
    access_token: str | None,
    api_key: str | None,
) -> tuple[bytes, str]:
    """Return file bytes and a vault filename (with extension)."""
    export = GOOGLE_EXPORT.get(item.mime_type)
    filename = _filename_for(item, export[1] if export else None)
    headers = _auth_headers(access_token)
    params = _auth_params(api_key)
    timeout = httpx.Timeout(60.0, connect=10.0)
    async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
        if export:
            params = {**params, "mimeType": export[0], "supportsAllDrives": "true"}
            url = f"{DRIVE_API}/files/{item.id}/export"
        else:
            params = {**params, "alt": "media", "supportsAllDrives": "true"}
            url = f"{DRIVE_API}/files/{item.id}"
        data = await _get_bytes(client, url, headers=headers, params=params)
    return data, filename


def skip_reason(item: DriveFile) -> str | None:
    mime = _normalize_mime(item.mime_type)
    if mime in SKIP_GOOGLE and mime != "application/vnd.google-apps.folder":
        return "Google app type is not a vault file"
    if mime in GOOGLE_EXPORT:
        return None
    if mime.startswith("application/vnd.google-apps"):
        return "Google app type is not a vault file"
    name = (item.name or "file").strip() or "file"
    ext = Path(name).suffix.lower()
    if ext in ALLOWED_EXTENSIONS:
        return None
    if mime in ALLOWED_MIME or MIME_TO_EXT.get(mime) or mime.startswith("image/"):
        return None
    if mime in SNIFF_LATER:
        return None
    return f"File type {ext or mime or 'unknown'} is not supported"


def _filename_for(item: DriveFile, forced_ext: str | None) -> str:
    name = (item.name or "file").strip() or "file"
    name = name.replace("\\", "_").replace("/", "_")
    if forced_ext:
        if Path(name).suffix.lower() != forced_ext:
            return f"{Path(name).stem}{forced_ext}"
        return name
    ext = Path(name).suffix.lower()
    if ext in ALLOWED_EXTENSIONS:
        return name
    guessed = MIME_TO_EXT.get(_normalize_mime(item.mime_type))
    if guessed:
        return f"{name}{guessed}"
    return name


def _normalize_mime(mime: str | None) -> str:
    raw = (mime or "").strip().lower()
    return MIME_ALIASES.get(raw, raw)


def _auth_headers(access_token: str | None) -> dict[str, str]:
    token = (access_token or "").strip()
    if not token:
        return {}
    if any(ch in token for ch in "\r\n\0") or len(token) > 4096:
        raise AppError("DRIVE_TOKEN", "Google Drive access token is invalid", 400)
    return {"Authorization": f"Bearer {token}"}


def _auth_params(api_key: str | None) -> dict[str, str]:
    key = (api_key or "").strip()
    if not key:
        return {}
    return {"key": key}


async def _walk_folder(
    client: httpx.AsyncClient,
    folder_id: str,
    *,
    depth: int,
    files: list[DriveFile],
    skipped: list[dict[str, str]],
    headers: dict[str, str],
    params_base: dict[str, str],
) -> None:
    if depth > MAX_DEPTH:
        skipped.append({"name": folder_id, "reason": "Folder is nested too deep"})
        return
    folder_id = _drive_id(folder_id)
    page_token = ""
    use_all_drives = True
    while True:
        params = {
            **params_base,
            "q": f"'{folder_id}' in parents and trashed = false",
            "fields": "nextPageToken,files(id,name,mimeType,size,shortcutDetails)",
            "pageSize": "100",
        }
        if use_all_drives:
            params["supportsAllDrives"] = "true"
            params["includeItemsFromAllDrives"] = "true"
        if page_token:
            params["pageToken"] = page_token
        payload = await _get_json(client, f"{DRIVE_API}/files", headers=headers, params=params)
        rows = list(payload.get("files") or [])
        if not rows and not page_token and use_all_drives:
            use_all_drives = False
            continue
        for raw in rows:
            mime = str(raw.get("mimeType") or "")
            file_id = str(raw.get("id") or "")
            name = str(raw.get("name") or "file")
            if mime == "application/vnd.google-apps.shortcut":
                details = raw.get("shortcutDetails") or {}
                if not details.get("targetId"):
                    meta = await _get_json(
                        client,
                        f"{DRIVE_API}/files/{file_id}",
                        headers=headers,
                        params={
                            **params_base,
                            "fields": "id,name,mimeType,shortcutDetails",
                            "supportsAllDrives": "true",
                        },
                    )
                    details = meta.get("shortcutDetails") or {}
                    name = str(meta.get("name") or name)
                target = details.get("targetId")
                target_mime = details.get("targetMimeType") or ""
                if target and DRIVE_ID_RE.fullmatch(str(target)):
                    file_id = str(target)
                    mime = str(target_mime)
                else:
                    skipped.append({"name": name, "reason": "Shortcut has no target"})
                    continue
            if not DRIVE_ID_RE.fullmatch(file_id):
                skipped.append({"name": name, "reason": "Invalid Google Drive id"})
                continue
            if mime == "application/vnd.google-apps.folder":
                await _walk_folder(
                    client,
                    file_id,
                    depth=depth + 1,
                    files=files,
                    skipped=skipped,
                    headers=headers,
                    params_base=params_base,
                )
                continue
            item = DriveFile(file_id, name, mime, _int_or_none(raw.get("size")))
            reason = skip_reason(item)
            if reason:
                skipped.append({"name": name, "reason": reason})
                continue
            if item.size is not None and item.size > settings.max_upload_size:
                skipped.append({"name": name, "reason": "File is larger than the vault limit"})
                continue
            if len(files) >= MAX_FILES:
                skipped.append({"name": name, "reason": f"Import stops after {MAX_FILES} files"})
                continue
            files.append(item)
        page_token = str(payload.get("nextPageToken") or "")
        if not page_token:
            break


async def _get_json(
    client: httpx.AsyncClient,
    url: str,
    *,
    headers: dict[str, str],
    params: dict[str, str],
) -> dict:
    try:
        response = await client.get(url, headers=headers, params=params)
    except httpx.HTTPError as exc:
        raise AppError("DRIVE_UNREACHABLE", "Could not reach Google Drive", 502) from exc
    if response.status_code in {401, 403}:
        raise AppError(
            "DRIVE_FORBIDDEN",
            _drive_http_message(response, "Google Drive did not allow this folder. Open the link, make sure it is shared, then allow Drive access."),
            403,
        )
    if response.status_code == 404:
        raise AppError("DRIVE_NOT_FOUND", "That Drive folder was not found", 404)
    if response.status_code >= 400:
        raise AppError("DRIVE_ERROR", _drive_http_message(response, "Google Drive could not list that folder"), 400)
    payload = response.json()
    if not isinstance(payload, dict):
        raise AppError("DRIVE_ERROR", "Google Drive returned an unexpected response", 502)
    return payload


async def _get_bytes(
    client: httpx.AsyncClient,
    url: str,
    *,
    headers: dict[str, str],
    params: dict[str, str],
) -> bytes:
    limit = settings.max_upload_size
    try:
        async with client.stream("GET", url, headers=headers, params=params) as response:
            if response.status_code in {401, 403}:
                raise AppError("DRIVE_FORBIDDEN", "Google Drive did not allow one of the files", 403)
            if response.status_code == 404:
                raise AppError("DRIVE_NOT_FOUND", "A file in that folder was not found", 404)
            if response.status_code >= 400:
                raise AppError("DRIVE_ERROR", "Google Drive could not download a file", 400)
            length = response.headers.get("content-length")
            if length and length.isdigit() and int(length) > limit:
                raise AppError("FILE_TOO_LARGE", "A file in that folder is larger than the vault limit", 413)
            chunks: list[bytes] = []
            total = 0
            async for chunk in response.aiter_bytes():
                total += len(chunk)
                if total > limit:
                    raise AppError("FILE_TOO_LARGE", "A file in that folder is larger than the vault limit", 413)
                chunks.append(chunk)
            data = b"".join(chunks)
    except AppError:
        raise
    except httpx.HTTPError as exc:
        raise AppError("DRIVE_UNREACHABLE", "Could not download from Google Drive", 502) from exc
    if not data:
        raise AppError("EMPTY_FILE", "A file in that folder is empty", 400)
    if data[:1] == b"{" and b"error" in data[:200]:
        raise AppError("DRIVE_ERROR", "Google Drive could not download a file", 400)
    return data


def _int_or_none(value: object) -> int | None:
    try:
        if value is None or value == "":
            return None
        return int(value)
    except (TypeError, ValueError):
        return None


def _drive_http_message(response: httpx.Response, fallback: str) -> str:
    try:
        payload = response.json()
        error = payload.get("error") if isinstance(payload, dict) else None
        text = ""
        if isinstance(error, dict):
            text = str(error.get("message") or "")
            errors = error.get("errors") or []
            if errors and isinstance(errors, list) and isinstance(errors[0], dict):
                reason = str(errors[0].get("reason") or "")
                if reason == "accessNotConfigured":
                    return "Enable the Google Drive API on the Google Cloud project used for sign-in."
        elif isinstance(error, str):
            text = error
        lowered = text.lower()
        if "accessnotconfigured" in lowered or "drive api" in lowered:
            return "Enable the Google Drive API on the Google Cloud project used for sign-in."
    except Exception:
        return fallback
    return fallback
