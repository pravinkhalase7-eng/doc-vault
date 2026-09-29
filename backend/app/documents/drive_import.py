"""Import files from a shared Google Drive folder into the vault."""

from __future__ import annotations

import re
from html import unescape
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlencode, urlparse, urlunparse

import httpx

from app.config import get_settings
from app.exceptions import AppError
from app.storage.local import ALLOWED_EXTENSIONS, ALLOWED_MIME, EXT_TO_MIME

settings = get_settings()

DRIVE_API = "https://www.googleapis.com/drive/v3"
MAX_FILES = 400
MAX_DEPTH = 5
DRIVE_ID_RE = re.compile(r"^[a-zA-Z0-9_-]{10,128}$")
CHROME_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
)

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
    def __init__(
        self,
        file_id: str,
        name: str,
        mime_type: str,
        size: int | None = None,
        source: str = "api",
    ) -> None:
        self.id = file_id
        self.name = name
        self.mime_type = mime_type
        self.size = size
        self.source = source


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
    api_error: AppError | None = None
    async with httpx.AsyncClient(timeout=timeout, follow_redirects=True, headers={"User-Agent": CHROME_UA}) as client:
        await _walk_public_folder(client, folder_id, depth=0, files=files, skipped=skipped, seen=set())
        if files:
            return files, skipped
        if access_token or api_key:
            try:
                api_files: list[DriveFile] = []
                api_skipped: list[dict[str, str]] = []
                await _walk_folder(
                    client,
                    folder_id,
                    depth=0,
                    files=api_files,
                    skipped=api_skipped,
                    headers=headers,
                    params_base=params_base,
                )
                files.extend(api_files)
                skipped.extend(api_skipped)
            except AppError as exc:
                api_error = exc
        if not files and api_error:
            if api_error.code == "DRIVE_API_DISABLED":
                raise AppError(
                    "DRIVE_EMPTY",
                    "That folder is shared, but Google did not list its files. Open the link in a browser, or download the files and drop them here.",
                    400,
                )
            raise api_error
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
    timeout = httpx.Timeout(60.0, connect=10.0)
    async with httpx.AsyncClient(timeout=timeout, follow_redirects=True, headers={"User-Agent": CHROME_UA}) as client:
        if item.source == "public" or not (access_token or api_key):
            data = await _download_public_bytes(client, item.id)
            return data, filename
        headers = _auth_headers(access_token)
        params = _auth_params(api_key)
        try:
            if export:
                params = {**params, "mimeType": export[0], "supportsAllDrives": "true"}
                url = f"{DRIVE_API}/files/{item.id}/export"
            else:
                params = {**params, "alt": "media", "supportsAllDrives": "true"}
                url = f"{DRIVE_API}/files/{item.id}"
            data = await _get_bytes(client, url, headers=headers, params=params)
        except AppError as exc:
            if exc.code not in {"DRIVE_API_DISABLED", "DRIVE_FORBIDDEN", "DRIVE_ERROR"}:
                raise
            data = await _download_public_bytes(client, item.id)
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
                return
            files.append(item)
        page_token = str(payload.get("nextPageToken") or "")
        if not page_token:
            break


_ENTRY_RE = re.compile(
    r'id="entry-([a-zA-Z0-9_-]{10,128})"[^>]*>[\s\S]{0,1200}?class="flip-entry-title"[^>]*>([^<]+)',
    re.I,
)
_FILE_LINK_RE = re.compile(
    r"https://drive\.google\.com/file/d/([a-zA-Z0-9_-]{25,})/",
    re.I,
)
_DOCS_LINK_RE = re.compile(
    r"https://docs\.google\.com/(document|spreadsheets|presentation)/d/([a-zA-Z0-9_-]{25,})/",
    re.I,
)
_FOLDER_LINK_RE = re.compile(r"https://drive\.google\.com/drive/folders/([a-zA-Z0-9_-]{10,128})")
_DATA_ID_RE = re.compile(r'data-id="([a-zA-Z0-9_-]{25,})"')
_HREF_FILE_RE = re.compile(
    r'<a[^>]+href="https://drive\.google\.com/file/d/([a-zA-Z0-9_-]{25,})/[^"]*"[^>]*>([^<]*)',
    re.I,
)
_FORM_RE = re.compile(
    r'<form[^>]+id="download-form"[^>]*action="([^"]+)"[^>]*>([\s\S]{0,8000}?)</form>',
    re.I,
)
_HIDDEN_INPUT_RE = re.compile(r"<input[^>]*>", re.I)
_INPUT_NAME_RE = re.compile(r'\bname=["\']([^"\']+)["\']', re.I)
_INPUT_VALUE_RE = re.compile(r'\bvalue=["\']([^"\']*)["\']', re.I)
_DOWNLOAD_URL_JSON_RE = re.compile(r'"downloadUrl"\s*:\s*"([^"]+)"')
_UC_HREF_RE = re.compile(r'href="(/uc\?export=download[^"]+)"', re.I)
_PUBLIC_DOWNLOAD_HOSTS = {
    "drive.google.com",
    "docs.google.com",
    "drive.usercontent.google.com",
}


def parse_public_folder_listing(html: str, folder_id: str) -> tuple[list[DriveFile], list[str]]:
    """Parse Google's public embedded folder page into files and nested folder ids."""
    files: list[DriveFile] = []
    folders: list[str] = []
    seen_files: set[str] = set()
    seen_folders: set[str] = set()
    current = _drive_id(folder_id)
    text = (html or "").replace("&amp;", "&")

    def add_file(file_id: str, name: str, mime: str = "") -> None:
        if file_id == current or file_id in seen_files:
            return
        seen_files.add(file_id)
        files.append(DriveFile(file_id, (name or "file").strip() or "file", mime, source="public"))

    for match in _HREF_FILE_RE.finditer(text):
        add_file(match.group(1), match.group(2))
    for match in _ENTRY_RE.finditer(text):
        add_file(match.group(1), match.group(2))
    for file_id in _FILE_LINK_RE.findall(text):
        add_file(file_id, "file")
    for kind, file_id in _DOCS_LINK_RE.findall(text):
        mime = {
            "document": "application/vnd.google-apps.document",
            "spreadsheets": "application/vnd.google-apps.spreadsheet",
            "presentation": "application/vnd.google-apps.presentation",
        }.get(kind.lower(), "")
        add_file(file_id, "file", mime)
    if not files:
        for file_id in _DATA_ID_RE.findall(text):
            add_file(file_id, "file")
    for nested in _FOLDER_LINK_RE.findall(text):
        if nested == current or nested in seen_folders:
            continue
        seen_folders.add(nested)
        folders.append(nested)
    return files, folders


async def _walk_public_folder(
    client: httpx.AsyncClient,
    folder_id: str,
    *,
    depth: int,
    files: list[DriveFile],
    skipped: list[dict[str, str]],
    seen: set[str],
) -> None:
    if depth > MAX_DEPTH:
        skipped.append({"name": folder_id, "reason": "Folder is nested too deep"})
        return
    folder_id = _drive_id(folder_id)
    if folder_id in seen:
        return
    seen.add(folder_id)
    url = f"https://drive.google.com/embeddedfolderview?id={folder_id}"
    try:
        response = await client.get(url)
        if response.status_code >= 400 or (
            "file/d/" not in (response.text or "") and "flip-entry" not in (response.text or "")
        ):
            sharing = await client.get(f"https://drive.google.com/drive/folders/{folder_id}?usp=sharing")
            if sharing.status_code < 400:
                response = sharing
    except httpx.HTTPError as exc:
        raise AppError("DRIVE_UNREACHABLE", "Could not reach Google Drive", 502) from exc
    if response.status_code >= 400:
        skipped.append({"name": folder_id, "reason": "That shared folder is not public"})
        return
    found, nested = parse_public_folder_listing(response.text, folder_id)
    if not found and not nested:
        return
    for item in found:
        reason = skip_reason(item)
        if reason:
            skipped.append({"name": item.name, "reason": reason})
            continue
        if len(files) >= MAX_FILES:
            skipped.append({"name": item.name, "reason": f"Import stops after {MAX_FILES} files"})
            return
        files.append(item)
    for nested_id in nested:
        if len(files) >= MAX_FILES:
            return
        await _walk_public_folder(
            client,
            nested_id,
            depth=depth + 1,
            files=files,
            skipped=skipped,
            seen=seen,
        )


async def _download_public_bytes(client: httpx.AsyncClient, file_id: str) -> bytes:
    file_id = _drive_id(file_id)
    urls = [
        f"https://drive.google.com/uc?id={file_id}&export=download",
        f"https://drive.usercontent.google.com/download?id={file_id}&export=download&confirm=t",
    ]
    last_error: AppError | None = None
    for url in urls:
        try:
            return await _follow_public_download(client, url, file_id=file_id, hops=0)
        except AppError as exc:
            last_error = exc
    raise last_error or AppError("DRIVE_ERROR", "Google Drive could not download a file", 400)


async def _follow_public_download(
    client: httpx.AsyncClient,
    url: str,
    *,
    file_id: str,
    hops: int,
) -> bytes:
    if hops > 5:
        raise AppError("DRIVE_ERROR", "Google Drive could not download a file", 400)
    url = _safe_public_download_url(url)
    try:
        response = await client.get(url)
    except httpx.HTTPError as exc:
        raise AppError("DRIVE_UNREACHABLE", "Could not download from Google Drive", 502) from exc
    if response.status_code in {401, 403}:
        raise AppError("DRIVE_FORBIDDEN", "That Drive file is not shared for download", 403)
    if response.status_code == 404:
        raise AppError("DRIVE_NOT_FOUND", "A file in that folder was not found", 404)
    if response.status_code >= 400:
        raise AppError("DRIVE_ERROR", "Google Drive could not download a file", 400)
    data = response.content or b""
    ctype = (response.headers.get("content-type") or "").lower()
    disposition = (response.headers.get("content-disposition") or "").lower()
    if "attachment" in disposition or _looks_binary_download(ctype, data):
        return _limited_bytes(data)
    if ctype.startswith("text/html") or _looks_html(data):
        nxt = public_download_url_from_html(data.decode("utf-8", "replace"), file_id)
        if not nxt:
            raise AppError("DRIVE_FORBIDDEN", "That Drive file is not shared for download", 403)
        return await _follow_public_download(client, nxt, file_id=file_id, hops=hops + 1)
    if data[:1] == b"{" and b"error" in data[:200]:
        raise AppError("DRIVE_ERROR", "Google Drive could not download a file", 400)
    return _limited_bytes(data)


def public_download_url_from_html(html: str, file_id: str) -> str | None:
    """Turn Google's virus-scan / confirm HTML into the next download URL."""
    text = unescape(html or "").replace("&amp;", "&")
    form = _FORM_RE.search(text)
    if form:
        action = form.group(1).strip() or "https://drive.usercontent.google.com/download"
        parsed = urlparse(action)
        host = (parsed.hostname or "drive.usercontent.google.com").lower()
        path = parsed.path or "/download"
        query = parse_qs(parsed.query)
        for tag in _HIDDEN_INPUT_RE.findall(form.group(2)):
            name_match = _INPUT_NAME_RE.search(tag)
            if not name_match:
                continue
            value_match = _INPUT_VALUE_RE.search(tag)
            query[name_match.group(1)] = [value_match.group(1) if value_match else ""]
        query.setdefault("id", [file_id])
        query.setdefault("export", ["download"])
        url = urlunparse(("https", host, path, "", urlencode(query, doseq=True), ""))
        return _safe_public_download_url(url)
    href = _UC_HREF_RE.search(text)
    if href:
        return _safe_public_download_url("https://drive.google.com" + unescape(href.group(1)))
    json_url = _DOWNLOAD_URL_JSON_RE.search(text)
    if json_url:
        raw = json_url.group(1).replace("\\u003d", "=").replace("\\u0026", "&").replace("\\/", "/")
        return _safe_public_download_url(raw)
    uuid = re.search(r'name=["\']uuid["\'][^>]*value=["\']([^"\']+)["\']', text, re.I)
    confirm = re.search(r'name=["\']confirm["\'][^>]*value=["\']([^"\']+)["\']', text, re.I)
    if uuid or confirm:
        params = {"id": file_id, "export": "download", "confirm": (confirm.group(1) if confirm else "t")}
        if uuid:
            params["uuid"] = uuid.group(1)
        return _safe_public_download_url(
            "https://drive.usercontent.google.com/download?" + urlencode(params)
        )
    return None


def _safe_public_download_url(url: str) -> str:
    parsed = urlparse((url or "").strip())
    host = (parsed.hostname or "").lower()
    if parsed.scheme != "https" or host not in _PUBLIC_DOWNLOAD_HOSTS:
        raise AppError("DRIVE_ERROR", "Google Drive could not download a file", 400)
    return urlunparse(parsed)


def _looks_html(data: bytes) -> bool:
    head = data.lstrip()[:20].lower()
    return head.startswith(b"<!doctype html") or head.startswith(b"<html")


def _looks_binary_download(content_type: str, data: bytes) -> bool:
    if _looks_html(data):
        return False
    return content_type.startswith(
        ("image/", "application/pdf", "application/octet-stream", "application/zip", "application/vnd", "video/")
    ) or data.startswith((b"%PDF", b"\xff\xd8\xff", b"\x89PNG"))


def _limited_bytes(data: bytes) -> bytes:
    if not data:
        raise AppError("EMPTY_FILE", "A file in that folder is empty", 400)
    if len(data) > settings.max_upload_size:
        raise AppError("FILE_TOO_LARGE", "A file in that folder is larger than the vault limit", 413)
    return data


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
        if _drive_api_disabled(response):
            raise AppError(
                "DRIVE_API_DISABLED",
                "Enable the Google Drive API on the Google Cloud project used for sign-in.",
                403,
            )
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


def _drive_api_disabled(response: httpx.Response) -> bool:
    return "Drive API" in _drive_http_message(response, "") or "accessNotConfigured" in (response.text or "")


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
