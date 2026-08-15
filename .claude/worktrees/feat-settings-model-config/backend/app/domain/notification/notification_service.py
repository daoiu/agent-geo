"""Notification triggers: publish success/failure and monitor changes."""
from __future__ import annotations

import structlog

from app.domain.exceptions import NotificationError
from app.domain.notification.email_sender import send_email

logger = structlog.get_logger()


async def notify_publish_success(
    title: str, remote_url: str, site_name: str, recipient: str
) -> None:
    subject = f"[GEO 发布成功] {title}"
    body = f"""文章《{title}》已成功发布到 WordPress 站点 {site_name}。

查看文章：{remote_url}
"""
    try:
        await send_email(to=recipient, subject=subject, body=body)
    except NotificationError as e:
        logger.warning("notify_publish_success_failed", error=str(e))


async def notify_publish_failure(
    title: str, error: str, site_name: str, recipient: str
) -> None:
    subject = f"[GEO 发布失败] {title}"
    body = f"""文章《{title}》发布到 WordPress 站点 {site_name} 失败。

错误信息：{error}

请检查 WordPress 凭证、权限、站点 URL 等。
"""
    try:
        await send_email(to=recipient, subject=subject, body=body)
    except NotificationError as e:
        logger.warning("notify_publish_failure_failed", error=str(e))
