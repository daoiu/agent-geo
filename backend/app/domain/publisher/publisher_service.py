"""Orchestrates a single publish attempt: load article, decrypt creds, call WP, persist result."""
from __future__ import annotations

import structlog

import markdown

from app.core.config import Settings
from app.domain.exceptions import PublishError
from app.domain.publisher.wordpress import WordPressClient
from app.domain.security.encryption import decrypt
from app.models.orm_v02 import ArticleORM
from app.repositories.publisher_repo import PublishRepository

logger = structlog.get_logger()


class PublishService:
    def __init__(self, repo: PublishRepository, settings: Settings) -> None:
        self.repo = repo
        self.settings = settings

    async def execute_publish(self, publish_job_id: str) -> None:
        job = await self.repo.get_publish_job(publish_job_id)
        if job is None or job.status != "pending":
            return

        await self.repo.update_publish_job_status(publish_job_id, status="running")

        # Load related entities
        config = await self.repo.get_publisher_config(job.config_id)
        article = await self.repo.get_article(job.article_id)

        if config is None:
            await self._mark_failed(publish_job_id, "publisher config not found")
            return
        if article is None:
            await self._mark_failed(publish_job_id, "article not found")
            return
        if article.review_status != "approved":
            await self._mark_failed(
                publish_job_id,
                f"article not approved (current: {article.review_status})",
            )
            return

        # Decrypt + create WP client
        try:
            app_password = decrypt(config.app_password_encrypted)
        except Exception as e:  # noqa: BLE001
            await self._mark_failed(
                publish_job_id, f"failed to decrypt credentials: {e}"
            )
            return

        wp_client = WordPressClient(
            site_url=config.site_url,
            username=config.username,
            app_password=app_password,
            timeout=float(self.settings.publish_timeout_s),
        )

        try:
            # Convert Markdown → HTML
            html = markdown.markdown(
                article.content or "",
                extensions=["extra", "sane_lists", "toc"],
            )
            title = job.title_override or article.title or "Untitled"

            result = await wp_client.create_post(title=title, content=html)

            await self.repo.update_publish_job_success(
                publish_job_id,
                remote_post_id=result["id"],
                remote_url=result["link"],
            )
            logger.info(
                "publish_success",
                job_id=publish_job_id,
                remote_url=result["link"],
            )

            # Trigger success notification (notification_service added in Phase 4).
            # Wrapped in try/except so missing module / SMTP failure never blocks publish.
            try:
                from app.domain.notification.notification_service import (
                    notify_publish_success,
                )
                await notify_publish_success(
                    title=title,
                    remote_url=result["link"],
                    site_name=config.name,
                    recipient=self.settings.smtp_from or "",
                )
            except Exception as e:  # noqa: BLE001
                logger.warning("notification_failed", error=str(e))
        except PublishError as e:
            await self._mark_failed(publish_job_id, str(e))
        except Exception as e:  # noqa: BLE001
            logger.exception("publish_unexpected", job_id=publish_job_id)
            await self._mark_failed(publish_job_id, f"unexpected: {type(e).__name__}: {e}")
        finally:
            await wp_client.close()

    async def _mark_failed(self, job_id: str, error: str) -> None:
        await self.repo.update_publish_job_status(job_id, status="failed", error=error)
        logger.warning("publish_failed", job_id=job_id, error=error)
        try:
            from app.domain.notification.notification_service import notify_publish_failure
            await notify_publish_failure(
                title="(unknown)", error=error, site_name="(unknown)",
                recipient=self.settings.smtp_from or "",
            )
        except Exception:  # noqa: BLE001
            pass
