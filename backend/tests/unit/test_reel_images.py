from pathlib import Path

from PIL import Image

from app.config import get_settings
from app.documents.ocr import generate_reel_images, reel_preview_is_sideways
from app.storage.local import thumbnail_path


def _sideways_phone_jpeg(dest: Path) -> None:
    """Landscape pixels + EXIF orientation 6 — iPhone portrait photo."""
    image = Image.new("RGB", (80, 40), (200, 40, 40))
    exif = image.getexif()
    exif[0x0112] = 6
    image.save(dest, format="JPEG", exif=exif)


def test_sideways_exif_is_detected(tmp_path: Path):
    src = tmp_path / "phone.jpg"
    thumb = tmp_path / "thumb.jpg"
    _sideways_phone_jpeg(src)
    Image.new("RGB", (80, 40), (10, 10, 10)).save(thumb, format="JPEG")
    assert reel_preview_is_sideways(src, thumb) is True


async def test_reel_jpeg_applies_exif_rotation(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("STORAGE_ROOT", str(tmp_path))
    get_settings.cache_clear()
    monkeypatch.setattr("app.storage.local.settings", get_settings())
    src = tmp_path / "phone.jpg"
    _sideways_phone_jpeg(src)
    thumb_key, preview_key = await generate_reel_images(src, "user-1", "doc-1", "image/jpeg")
    assert thumb_key
    assert preview_key
    thumb = thumbnail_path("user-1", "doc-1")
    with Image.open(thumb) as out:
        width, height = out.size
    assert height > width
    assert reel_preview_is_sideways(src, thumb) is False
    get_settings.cache_clear()
