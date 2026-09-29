import pytest

from app.documents.drive_import import MAX_FILES, parse_drive_folder_id, skip_reason, DriveFile
from app.exceptions import AppError


def test_parse_drive_folder_sharing_link():
    folder_id = parse_drive_folder_id(
        "https://drive.google.com/drive/folders/185s0JmcOYcX6fiJ24az5IzvMIgh8Snwj?usp=sharing"
    )
    assert folder_id == "185s0JmcOYcX6fiJ24az5IzvMIgh8Snwj"


def test_parse_drive_folder_user_path_and_raw_id():
    assert (
        parse_drive_folder_id("https://drive.google.com/drive/u/0/folders/185s0JmcOYcX6fiJ24az5IzvMIgh8Snwj")
        == "185s0JmcOYcX6fiJ24az5IzvMIgh8Snwj"
    )
    assert parse_drive_folder_id("185s0JmcOYcX6fiJ24az5IzvMIgh8Snwj") == "185s0JmcOYcX6fiJ24az5IzvMIgh8Snwj"


def test_parse_drive_folder_rejects_other_sites():
    with pytest.raises(AppError) as err:
        parse_drive_folder_id("https://example.com/folders/185s0JmcOYcX6fiJ24az5IzvMIgh8Snwj")
    assert err.value.code == "DRIVE_URL"


def test_skip_reason_keeps_pdf_and_exports_docs():
    assert skip_reason(DriveFile("abc1234567", "pass.pdf", "application/pdf")) is None
    assert skip_reason(DriveFile("abc1234567", "Notes", "application/vnd.google-apps.document")) is None
    assert skip_reason(DriveFile("abc1234567", "Form", "application/vnd.google-apps.form"))


def test_import_cap_covers_large_photo_folders():
    assert MAX_FILES >= 250


def test_skip_reason_keeps_photos_without_an_extension():
    assert skip_reason(DriveFile("abc1234567", "Photo from Shared", "image/jpeg")) is None
    assert skip_reason(DriveFile("abc1234567", "Photo from Shared", "application/octet-stream")) is None
    assert skip_reason(DriveFile("abc1234567", "Photo from Shared", "")) is None


def test_parse_public_folder_listing_reads_embedded_entries():
    from app.documents.drive_import import parse_public_folder_listing

    html = """
    <div class="flip-entry" id="entry-0BxyzABCDEFGHIJKLMNOP">
      <div class="flip-entry-title">Photo from Shared</div>
    </div>
    <a href="https://drive.google.com/file/d/1abcFileIdWithoutEntry1234567/view?usp=sharing">Photo from Shared</a>
    """
    files, folders = parse_public_folder_listing(html, "1opLsKJk2k3jdPnWTwnfKIEDMol4amzwS")
    names = {item.name for item in files}
    ids = {item.id for item in files}
    assert "Photo from Shared" in names
    assert "0BxyzABCDEFGHIJKLMNOP" in ids
    assert "1abcFileIdWithoutEntry1234567" in ids
    assert folders == []
    named = next(item for item in files if item.id == "1abcFileIdWithoutEntry1234567")
    assert named.name == "Photo from Shared"


def test_public_download_url_from_confirm_form():
    from app.documents.drive_import import public_download_url_from_html

    html = """
    <form id="download-form" action="https://drive.usercontent.google.com/download">
      <input type="hidden" name="id" value="1abcFileIdWithoutEntry1234567">
      <input type="hidden" name="export" value="download">
      <input type="hidden" name="confirm" value="t">
      <input type="hidden" name="uuid" value="11111111-2222-3333-4444-555555555555">
    </form>
    """
    url = public_download_url_from_html(html, "1abcFileIdWithoutEntry1234567")
    assert url is not None
    assert "drive.usercontent.google.com" in url
    assert "uuid=11111111-2222-3333-4444-555555555555" in url
    assert "confirm=t" in url
