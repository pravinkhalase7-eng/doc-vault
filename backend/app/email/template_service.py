from app.email.smtp_service import render_template, send_email


async def send_templated(to_address: str, template: str, subject: str, **context: object) -> bool:
    html = render_template(f"{template}.html", **context)
    return await send_email(to_address, subject, html)
