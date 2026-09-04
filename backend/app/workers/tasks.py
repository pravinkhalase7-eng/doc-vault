import asyncio
from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from app.database import SessionLocal
from app.config import get_settings
from app.documents.processing import process_document
from app.email.digest_service import send_daily_briefings, send_weekly_reports
from app.email.notification_service import notify
from app.models.collection import Reminder
from app.models.document import Document
from app.models.notification import Notification
from app.models.user import User
from app.reminders.service import deliver_reminder_call, due_call_reminders
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
                already = await db.scalar(
                    select(Notification.id).where(
                        Notification.user_id == user.id,
                        Notification.kind == "expiry",
                        Notification.link == f"{settings.app_url}/documents/{doc.id}",
                    )
                )
                if already:
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


@celery_app.task(name="app.workers.tasks.fire_reminder_call")
def fire_reminder_call(reminder_id: str) -> str:
    async def _inner() -> str:
        async with SessionLocal() as db:
            reminder = await db.get(Reminder, reminder_id)
            if not reminder:
                return "missing"
            status = await deliver_reminder_call(db, reminder)
            await db.commit()
            return status

    return asyncio.run(_inner())


@celery_app.task(name="app.workers.tasks.fire_due_reminder_calls")
def fire_due_reminder_calls() -> int:
    async def _inner() -> int:
        async with SessionLocal() as db:
            rows = await due_call_reminders(db)
            for reminder in rows:
                try:
                    await deliver_reminder_call(db, reminder)
                    await db.commit()
                except Exception:
                    await db.rollback()
            return len(rows)

    return asyncio.run(_inner())


@celery_app.task(name="app.workers.tasks.poll_shared_inbox")
def poll_shared_inbox() -> dict:
    async def _inner() -> dict:
        if not settings.imap_configured:
            return {"skipped": True, "reason": "IMAP_DISABLED", "processed": 0}
        from app.documents.processing import enqueue_document_processing
        from app.email.imap_ingest import poll_shared_inbox as poll

        async with SessionLocal() as db:
            result = await poll(db)
            for doc_id in result.pop("process_ids", []) or []:
                await enqueue_document_processing(doc_id)
            return result

    return asyncio.run(_inner())
