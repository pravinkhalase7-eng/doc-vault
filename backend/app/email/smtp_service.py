from email.message import EmailMessage

from jinja2 import Environment, FileSystemLoader, select_autoescape

from app.config import get_settings
from app.logging import get_logger

log = get_logger("smtp")
settings = get_settings()

_env = Environment(
    loader=FileSystemLoader("app/email/templates"),
    autoescape=select_autoescape(["html"]),
)


async def send_email(to_address: str, subject: str, html: str, text: str | None = None) -> bool:
    if not settings.smtp_configured:
        log.info("smtp_skipped", to=to_address, subject=subject)
        return False
    message = EmailMessage()
    message["From"] = f"{settings.email_from_name} <{settings.email_from}>"
    message["To"] = to_address
    message["Subject"] = subject
    message.set_content(text or "Open this message in an HTML email client.")
    message.add_alternative(html, subtype="html")
    try:
        import aiosmtplib

        await aiosmtplib.send(
            message,
            hostname=settings.smtp_host,
            port=settings.smtp_port,
            username=settings.smtp_username or None,
            password=settings.smtp_password or None,
            start_tls=settings.smtp_use_tls,
        )
        return True
    except Exception as exc:
        log.warning("smtp_failed", error=type(exc).__name__)
        return False


def render_template(name: str, **context: object) -> str:
    template = _env.get_template(name)
    return template.render(app_name=settings.app_name, app_url=settings.app_url, **context)
