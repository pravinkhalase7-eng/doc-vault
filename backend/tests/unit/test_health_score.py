from datetime import date

from app.services.health_score import compute_health


class _FakeResult:
    def __init__(self, rows):
        self._rows = rows

    def all(self):
        return self._rows


class _FakeScalars:
    def __init__(self, rows):
        self._rows = rows

    async def scalars(self, _query):
        return _FakeResult(self._rows)


class _EmptyDB:
    async def scalars(self, _query):
        return _FakeResult([])


class _Doc:
    def __init__(self, *, category_id=None, expiry_date=None, verification_status=None, exclude_from_ai=False):
        from app.models.enums import VerificationStatus

        self.category_id = category_id
        self.expiry_date = expiry_date
        self.verification_status = verification_status or VerificationStatus.USER_CONFIRMED
        self.exclude_from_ai = exclude_from_ai


import pytest


@pytest.mark.asyncio
async def test_empty_vault_health_is_full_score():
    health = await compute_health(_EmptyDB(), "user-1")
    assert health["score"] == 100
    assert health["expiring_soon"] == 0
    assert health["total"] == 0
    assert "Upload your first document" in health["notes"][0]


@pytest.mark.asyncio
async def test_health_counts_expired_and_soon(monkeypatch):
    from app.models.enums import VerificationStatus
    from app.services import health_score

    today = date(2026, 9, 4)

    class _Today:
        @staticmethod
        def today():
            return today

    monkeypatch.setattr(health_score, "date", _Today)
    docs = [
        _Doc(category_id="g", expiry_date=date(2026, 8, 1), verification_status=VerificationStatus.USER_CONFIRMED),
        _Doc(category_id="g", expiry_date=date(2026, 9, 20), verification_status=VerificationStatus.USER_CONFIRMED),
        _Doc(category_id="g", expiry_date=date(2027, 1, 1), verification_status=VerificationStatus.USER_CONFIRMED),
    ]
    health = await compute_health(_FakeScalars(docs), "user-1")
    assert health["expired"] == 1
    assert health["expiring_soon"] == 1
    assert health["total"] == 3
    assert any("expiring soon" in note for note in health["notes"])
