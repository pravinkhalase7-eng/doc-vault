from pathlib import Path

from app.documents.export import safe_zip_component, unique_arcname, write_vault_zip


def test_safe_zip_component_strips_paths():
    assert ".." not in safe_zip_component("../etc/passwd")
    assert "/" not in safe_zip_component("a/b\\c")
    assert safe_zip_component("") == "file"


def test_unique_arcname_avoids_collisions():
    used: set[str] = set()
    first = unique_arcname(used, "Passport", "scan.jpg")
    second = unique_arcname(used, "Passport", "scan.jpg")
    assert first == "Passport/scan.jpg"
    assert second == "Passport/scan-2.jpg"
    assert first.lower() in used


def test_write_vault_zip_skips_missing_and_indexes(tmp_path: Path):
    present = tmp_path / "a.txt"
    present.write_text("hello")
    missing = tmp_path / "gone.txt"
    dest = tmp_path / "vault.zip"
    count = write_vault_zip(
        dest,
        [
            ("Default/a.txt", present, {"folder": "Default", "title": "A", "filename": "a.txt", "mime_type": "text/plain", "bytes": "5"}),
            ("Default/gone.txt", missing, {"folder": "Default", "title": "Gone", "filename": "gone.txt", "mime_type": "text/plain", "bytes": "0"}),
        ],
    )
    assert count == 1
    assert dest.is_file()
    import zipfile

    with zipfile.ZipFile(dest) as zf:
        names = zf.namelist()
        assert "Default/a.txt" in names
        assert "Default/gone.txt" not in names
        assert "vault-index.csv" in names
        index = zf.read("vault-index.csv").decode()
        assert "A" in index
        assert "Gone" not in index
