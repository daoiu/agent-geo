"""SMTP email sender using aiosmtplib."""
from __future__ import annotations

from email.mime.text import MIMEText

import aiosmtplib
import structlog

from app.core.config import get_settings
from app.domain.exceptions import NotificationError

logger = structlog.get_logger()


async def send_email(to: str, subject: str, body: str) -> None:
    settings = get_settings()
    if not settings.smtp_host:
        raise NotificationError("SMTP not configured (SMTP_HOST is empty)")

    msg = MIMEText(body, "plain", "utf-8")
    msg["Subject"] = subject
    msg["From"] = settings.smtp_from or settings.smtp_user
    msg["To"] = to

    try:
        await aiosmtplib.send(
            msg,
            hostname=settings.smtp_host,
            port=settings.smtp_port,
            username=settings.smtp_user,
            password=settings.smtp_password,
            start_tls=settings.smtp_use_tls,
        )
        logger.info("email_sent", to=to, subject=subject)
    except Exception as e:  # noqa: BLE001
        logger.warning("email_send_failed", error=str(e))
        raise NotificationError(str(e)) from e
