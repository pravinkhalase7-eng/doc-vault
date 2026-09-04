from datetime import date

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.document import Document, DocumentMetadata
from app.models.enums import VerificationStatus


async def compute_health(db: AsyncSession, user_id: str) -> dict:
    docs = (
        await db.scalars(
            select(Document).where(
                Document.user_id == user_id,
                Document.deleted_at.is_(None),
                Document.trashed_at.is_(None),
            )
        )
    ).all()
    total = len(docs)
    if total == 0:
        return {
            "score": 100,
            "organization": 100,
            "metadata": 100,
            "security": 100,
            "expiry": 100,
            "duplicate": 100,
            "notes": ["Upload your first document to start tracking vault health."],
            "expiring_soon": 0,
            "expired": 0,
            "unverified": 0,
            "total": 0,
        }
    categorized = sum(1 for d in docs if d.category_id)
    with_expiry = sum(1 for d in docs if d.expiry_date)
    expired = sum(1 for d in docs if d.expiry_date and d.expiry_date < date.today())
    today = date.today()
    expiring = sum(
        1
        for d in docs
        if d.expiry_date and 0 <= (d.expiry_date - today).days <= 30
    )
    unverified = sum(1 for d in docs if d.verification_status == VerificationStatus.UNVERIFIED)
    excluded = sum(1 for d in docs if d.exclude_from_ai)
    org = int(categorized / total * 100)
    meta = int((total - unverified) / total * 100) if total else 100
    expiry_score = max(0, 100 - expired * 15 - max(0, (total - with_expiry)) * 4)
    security = 90 if excluded or total else 80
    duplicate_score = 100
    notes = []
    if expiring:
        notes.append(f"{expiring} documents expiring soon")
    if expired:
        notes.append(f"{expired} expired documents")
    if unverified:
        notes.append(f"{unverified} documents missing confirmed metadata")
    score = int((org + meta + expiry_score + security + duplicate_score) / 5)
    return {
        "score": score,
        "organization": org,
        "metadata": meta,
        "security": security,
        "expiry": expiry_score,
        "duplicate": duplicate_score,
        "notes": notes or ["Well organized"],
        "expiring_soon": expiring,
        "expired": expired,
        "unverified": unverified,
        "total": total,
    }
