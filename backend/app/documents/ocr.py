"""Local OCR + text extraction. Original files never leave the VPS."""

from __future__ import annotations

import io
import re
from pathlib import Path

from app.logging import get_logger
from app.storage.local import thumbnail_path, write_bytes

log = get_logger("ocr")

DATE_RE = re.compile(r"\b(\d{1,2}[-/]\d{1,2}[-/]\d{2,4}|\d{4}[-/]\d{1,2}[-/]\d{1,2})\b")


class OCREngine:
    name = "base"

    def extract(self, path: Path, mime: str) -> dict:
        raise NotImplementedError


class TesseractEngine(OCREngine):
    name = "tesseract"

    def extract(self, path: Path, mime: str) -> dict:
        text = ""
        pages: list[dict] = []
        page_count = 1
        if mime == "application/pdf" or path.suffix.lower() == ".pdf":
            text, pages, page_count = _extract_pdf(path)
        elif mime.startswith("image/") or path.suffix.lower() in {
            ".jpg",
            ".jpeg",
            ".png",
            ".webp",
            ".gif",
            ".bmp",
            ".tif",
            ".tiff",
            ".heic",
            ".heif",
            ".avif",
        }:
            text, pages = _extract_image(path)
        elif path.suffix.lower() == ".txt":
            text = path.read_text(encoding="utf-8", errors="ignore")
            pages = [{"page": 1, "text": text, "confidence": 1.0}]
        elif path.suffix.lower() == ".docx":
            text = _extract_docx(path)
            pages = [{"page": 1, "text": text, "confidence": 1.0}]
        elif path.suffix.lower() == ".xlsx":
            text = _extract_xlsx(path)
            pages = [{"page": 1, "text": text, "confidence": 1.0}]
        return {"text": text.strip(), "pages": pages, "page_count": page_count, "engine": self.name}


def _extract_pdf(path: Path) -> tuple[str, list[dict], int]:
    try:
        from pypdf import PdfReader

        reader = PdfReader(str(path))
        pages = []
        texts = []
        for i, page in enumerate(reader.pages, start=1):
            page_text = page.extract_text() or ""
            texts.append(page_text)
            pages.append({"page": i, "text": page_text, "confidence": 0.99 if page_text.strip() else 0.0})
        combined = "\n\n".join(texts)
        if combined.strip():
            return combined, pages, len(reader.pages)
        return _ocr_pdf_images(path, len(reader.pages))
    except Exception as exc:
        log.warning("pdf_extract_failed", error=str(exc))
        return "", [], 1


def _ocr_pdf_images(path: Path, page_count: int) -> tuple[str, list[dict], int]:
    try:
        from pdf2image import convert_from_path
        import pytesseract

        images = convert_from_path(str(path), dpi=200)
        pages = []
        texts = []
        for i, image in enumerate(images, start=1):
            page_text = pytesseract.image_to_string(image)
            texts.append(page_text)
            pages.append({"page": i, "text": page_text, "confidence": 0.8})
        return "\n\n".join(texts), pages, len(images) or page_count
    except Exception as exc:
        log.info("ocr_pdf_unavailable", error=str(exc))
        return "", [], page_count


def _extract_image(path: Path) -> tuple[str, list[dict]]:
    try:
        from PIL import Image
        import pytesseract

        image = Image.open(path)
        text = pytesseract.image_to_string(image)
        return text, [{"page": 1, "text": text, "confidence": 0.8}]
    except Exception as exc:
        log.info("ocr_image_unavailable", error=str(exc))
        return "", []


def _extract_docx(path: Path) -> str:
    try:
        from zipfile import ZipFile
        import xml.etree.ElementTree as ET

        with ZipFile(path) as zf:
            xml = zf.read("word/document.xml")
        root = ET.fromstring(xml)
        texts = [node.text for node in root.iter() if node.text]
        return "\n".join(texts)
    except Exception:
        return ""


def _extract_xlsx(path: Path) -> str:
    try:
        from zipfile import ZipFile
        import xml.etree.ElementTree as ET

        with ZipFile(path) as zf:
            names = [n for n in zf.namelist() if n.startswith("xl/sharedStrings")]
            if not names:
                return ""
            xml = zf.read(names[0])
        root = ET.fromstring(xml)
        texts = [node.text for node in root.iter() if node.text]
        return "\n".join(texts)
    except Exception:
        return ""


def get_ocr_engine(name: str | None = None) -> OCREngine:
    return TesseractEngine()


async def generate_thumbnail(src: Path, user_id: str, document_id: str, mime: str) -> str | None:
    try:
        from PIL import Image

        dest = thumbnail_path(user_id, document_id)
        if mime == "application/pdf":
            try:
                from pdf2image import convert_from_path

                images = convert_from_path(str(src), dpi=72, first_page=1, last_page=1)
                if not images:
                    return None
                image = images[0]
            except Exception:
                return None
        elif mime.startswith("image/"):
            image = Image.open(src)
        else:
            return None
        image = image.convert("RGB")
        image.thumbnail((480, 640))
        buf = io.BytesIO()
        image.save(buf, format="JPEG", quality=82)
        await write_bytes(dest, buf.getvalue())
        from app.storage.local import relative_key

        return relative_key(dest)
    except Exception as exc:
        log.info("thumbnail_failed", error=str(exc))
        return None
