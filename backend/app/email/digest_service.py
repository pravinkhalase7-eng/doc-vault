from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.ai.router import get_router
from app.config import get_settings
from app.email.notification_service import notify
from app.models.document import Document
from app.models.user import User
from app.services.health_score import compute_health

settings = get_settings()


async def send_daily_briefings(db: AsyncSession) -> int:
    users = (
        await db.scalars(
            select(User).options(selectinload(User.preferences)).where(User.deleted_at.is_(None), User.is_active.is_(True))
        )
    ).all()
    count = 0
    for user in users:
        if not user.preferences or not user.preferences.daily_briefing_enabled:
            continue
        health = await compute_health(db, user.id)
        until = date.today() + timedelta(days=30)
        expiring = (
            await db.scalars(
                select(Document).where(
                    Document.user_id == user.id,
                    Document.expiry_date.is_not(None),
                    Document.expiry_date <= until,
                    Document.deleted_at.is_(None),
                    Document.trashed_at.is_(None),
                )
            )
        ).all()
        summary_input = {
            "question": "Write a short daily briefing from this metadata only.",
            "records": [
                {"title": d.title, "expiry_date": d.expiry_date.isoformat() if d.expiry_date else None}
                for d in expiring
            ],
            "health": health,
        }
        router = get_router()
        summary = await router.reason(
            summary_input, external_allowed=bool(user.preferences.external_ai_enabled)
        )
        await notify(
            db,
            user,
            kind="daily_briefing",
            title="Your DocVault Briefing",
            body=summary,
            template="daily_briefing",
            email_context={
                "summary": summary,
                "health": health,
                "expiring": [d.title for d in expiring],
            },
        )
        count += 1
    return count


async def send_weekly_reports(db: AsyncSession) -> int:
    users = (
        await db.scalars(
            select(User).options(selectinload(User.preferences)).where(User.deleted_at.is_(None), User.is_active.is_(True))
        )
    ).all()
    count = 0
    for user in users:
        if not user.preferences or not user.preferences.weekly_report_enabled:
            continue
        health = await compute_health(db, user.id)
        await notify(
            db,
            user,
            kind="weekly_report",
            title="Weekly document health report",
            body=f"Document health: {health['score']}/100",
            template="weekly_report",
            email_context={"health": health},
        )
        count += 1
    return count
