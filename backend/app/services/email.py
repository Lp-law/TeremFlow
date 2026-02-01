from __future__ import annotations

import smtplib
from email.message import EmailMessage

from app.core.config import settings


def send_email(*, subject: str, body: str, recipients: list[str]) -> None:
    """
    MVP email sending:
    - If SMTP is not configured, we print to logs (stdout) instead of sending.
    """
    if not recipients:
        return

    if not settings.smtp_host or not settings.smtp_from:
        print("[EMAIL][DRY_RUN]", {"to": recipients, "subject": subject, "body": body})
        return

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = settings.smtp_from
    msg["To"] = ", ".join(recipients)
    msg.set_content(body)

    with smtplib.SMTP(settings.smtp_host, settings.smtp_port) as s:
        s.starttls()
        if settings.smtp_username and settings.smtp_password:
            s.login(settings.smtp_username, settings.smtp_password)
        s.send_message(msg)


