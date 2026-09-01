import asyncio
from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from app.config import get_settings
from app.database import SessionLocal
from app.documents.processing import process_document
from app.email.digest_service import send_daily_briefings, send_weekly_reports
from app.email.notification_service import notify
from app.models.document import Document
from app.models.user import User
from app.workers.celery_app import celery_app

settings = get_settings()


def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


@celery_app.task(name="app.workers.tasks.process_document_task")
def process_document_task(document_id: str) -> None:
    async def _inner() -> None:
        async with SessionLocal() as db:
            await process_document(db, document_id)

    asyncio.run(_inner())


@celery_app.task(name="app.workers.tasks.scan_expiries")
def scan_expiries() -> None:
    async def _inner() -> None:
        async with SessionLocal() as db:
            soon = (datetime.now(UTC) + timedelta(days=30)).date()
            docs = (
                await db.scalars(
                    select(Document).where(
                        Document.expiry_date.is_not(None),
                        Document.expiry_date <= soon,
                        Document.deleted_at.is_(None),
                        Document.trashed_at.is_(None),
                    )
                )
            ).all()
            for doc in docs:
                user = await db.get(User, doc.user_id)
                if not user:
                    continue
                await notify(
                    db,
                    user,
                    kind="expiry",
                    title=f"{doc.title} is expiring",
                    body=f"{doc.title} expires on {doc.expiry_date}.",
                    template="document_expiry",
                    link=f"{settings.app_url}/documents/{doc.id}",
                )

    asyncio.run(_inner())


@celery_app.task(name="app.workers.tasks.daily_briefing")
def daily_briefing() -> None:
    async def _inner() -> None:
        async with SessionLocal() as db:
            await send_daily_briefings(db)

    asyncio.run(_inner())


@celery_app.task(name="app.workers.tasks.weekly_report")
def weekly_report() -> None:
    async def _inner() -> None:
        async with SessionLocal() as db:
            await send_weekly_reports(db)

    asyncio.run(_inner())


@celery_app.task(name="app.workers.tasks.purge_trash")
def purge_trash() -> None:
    async def _inner() -> None:
        async with SessionLocal() as db:
            cutoff = datetime.now(UTC) - timedelta(days=settings.trash_retention_days)
            rows = (
                await db.scalars(
                    select(Document).where(Document.trashed_at.is_not(None), Document.trashed_at < cutoff)
                )
            ).all()
            from app.documents.service import permanently_delete

            for doc in rows:
                await permanently_delete(db, doc.user_id, doc.id)

    asyncio.run(_inner())
