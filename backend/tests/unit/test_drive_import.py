import pytest

from app.documents.drive_import import parse_drive_folder_id, skip_reason, DriveFile
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


def test_skip_reason_keeps_photos_without_an_extension():
    assert skip_reason(DriveFile("abc1234567", "Photo from Shared", "image/jpeg")) is None
    assert skip_reason(DriveFile("abc1234567", "Photo from Shared", "application/octet-stream")) is None
    assert skip_reason(DriveFile("abc1234567", "Photo from Shared", "")) is None
