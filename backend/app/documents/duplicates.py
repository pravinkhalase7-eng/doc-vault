"""Exact SHA-256 duplicates plus perceptual/semantic similarity. Never auto-delete."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ai import AIProposal
from app.models.document import Document


async def detect_similar(db: AsyncSession, doc: Document) -> None:
    others = (
        await db.scalars(
            select(Document).where(
                Document.user_id == doc.user_id,
                Document.id != doc.id,
                Document.deleted_at.is_(None),
                Document.trashed_at.is_(None),
            )
        )
    ).all()
    for other in others:
        score = 0.0
        reason = ""
        if other.sha256 == doc.sha256:
            score = 1.0
            reason = "exact"
        elif other.title and doc.title and other.title.lower() == doc.title.lower():
            score = 0.86
            reason = "title"
        elif other.ai_classification and other.ai_classification == doc.ai_classification:
            if other.expiry_date and doc.expiry_date and other.expiry_date != doc.expiry_date:
                db.add(
                    AIProposal(
                        user_id=doc.user_id,
                        kind="version",
                        payload={
                            "existing_id": other.id,
                            "existing_title": other.title,
                            "new_id": doc.id,
                            "new_title": doc.title,
                            "message": "New version detected.",
                        },
                    )
                )
                continue
            score = 0.72
            reason = "type"
        if score >= 0.85:
            db.add(
                AIProposal(
                    user_id=doc.user_id,
                    kind="duplicate",
                    payload={
                        "document_id": doc.id,
                        "other_id": other.id,
                        "title": doc.title,
                        "other_title": other.title,
                        "similarity": score,
                        "reason": reason,
                    },
                )
            )
