from pathlib import Path

from app.config import get_settings
from app.push.vapid import resolved_vapid_keys


def test_vapid_keys_persist(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("STORAGE_ROOT", str(tmp_path))
    get_settings.cache_clear()
    public_a, private_a = resolved_vapid_keys()
    public_b, private_b = resolved_vapid_keys()
    assert public_a == public_b
    assert private_a == private_b
    assert (tmp_path / "vapid.json").exists()
    get_settings.cache_clear()
