from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.email.template_service import send_templated
from app.models.notification import EmailLog, Notification
from app.models.enums import NotificationChannel
from app.models.user import User

settings = get_settings()


async def notify(
    db: AsyncSession,
    user: User,
    *,
    kind: str,
    title: str,
    body: str,
    template: str | None = None,
    link: str | None = None,
    email_context: dict | None = None,
) -> None:
    db.add(
        Notification(
            user_id=user.id,
            title=title,
            body=body,
            kind=kind,
            channel=NotificationChannel.IN_APP,
            link=link,
        )
    )
    prefs = user.preferences
    if template and prefs and prefs.notification_email:
        log = EmailLog(
            user_id=user.id,
            to_address=user.email,
            template=template,
            subject=title,
            status="queued",
        )
        db.add(log)
        await db.flush()
        ok = await send_templated(user.email, template, title, **(email_context or {"body": body, "link": link}))
        log.status = "sent" if ok else "skipped"
    await db.commit()
