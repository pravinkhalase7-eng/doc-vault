"""Build a zip of a user's vault files (originals only, no trash)."""

from __future__ import annotations

import csv
import io
import re
import zipfile
from pathlib import Path

UNSAFE = re.compile(r'[\\/:*?"<>|\x00-\x1f]+')


def safe_zip_component(name: str, fallback: str = "file") -> str:
    cleaned = UNSAFE.sub("-", (name or "").strip()).strip(" .-")
    cleaned = cleaned.replace("..", ".")
    return (cleaned[:80] or fallback).rstrip(".")


def unique_arcname(used: set[str], folder: str, filename: str) -> str:
    folder_part = safe_zip_component(folder, "Unfiled")
    stem = safe_zip_component(Path(filename).stem, "file")
    ext = Path(filename).suffix.lower()
    if len(ext) > 8:
        ext = ""
    candidate = f"{folder_part}/{stem}{ext}"
    n = 2
    while candidate.lower() in used:
        candidate = f"{folder_part}/{stem}-{n}{ext}"
        n += 1
    used.add(candidate.lower())
    return candidate


def write_vault_zip(
    dest: Path,
    entries: list[tuple[str, Path, dict[str, str]]],
) -> int:
    """Write a zip to dest. entries are (arcname, source_path, index_row). Returns file count."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    index_buf = io.StringIO()
    writer = csv.DictWriter(
        index_buf,
        fieldnames=["folder", "title", "filename", "mime_type", "bytes"],
    )
    writer.writeheader()
    count = 0
    with zipfile.ZipFile(dest, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for arcname, source, row in entries:
            if not source.is_file():
                continue
            zf.write(source, arcname=arcname)
            writer.writerow(row)
            count += 1
        zf.writestr("vault-index.csv", index_buf.getvalue())
    return count
