"""Repository for WordPress publisher configs and publish jobs."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.orm_v02 import ArticleORM
from app.models.orm_v03 import PublisherConfigORM, PublishJobORM


class PublishRepository:
    """Data access for v0.3 publisher tables."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    # --- PublisherConfig ---

    async def create_publisher_config(
        self,
        name: str,
        site_url: str,
        username: str,
        app_password_encrypted: str,
        is_default: bool = False,
    ) -> PublisherConfigORM:
        pc = PublisherConfigORM(
            id=str(uuid.uuid4()),
            name=name,
            site_url=site_url,
            username=username,
            app_password_encrypted=app_password_encrypted,
            is_default=1 if is_default else 0,
        )
        self.session.add(pc)
        await self.session.commit()
        await self.session.refresh(pc)
        return pc

    async def get_publisher_config(self, id: str) -> PublisherConfigORM | None:
        result = await self.session.execute(
            select(PublisherConfigORM).where(PublisherConfigORM.id == id)
        )
        return result.scalar_one_or_none()

    async def list_publisher_configs(self) -> list[PublisherConfigORM]:
        result = await self.session.execute(
            select(PublisherConfigORM).order_by(PublisherConfigORM.created_at.desc())
        )
        return list(result.scalars().all())

    async def update_publisher_config(
        self,
        id: str,
        name: str | None = None,
        site_url: str | None = None,
        username: str | None = None,
        app_password_encrypted: str | None = None,
        is_default: bool | None = None,
    ) -> None:
        pc = await self.get_publisher_config(id)
        if pc is None:
            return
        if name is not None:
            pc.name = name
        if site_url is not None:
            pc.site_url = site_url
        if username is not None:
            pc.username = username
        if app_password_encrypted is not None:
            pc.app_password_encrypted = app_password_encrypted
        if is_default is not None:
            pc.is_default = 1 if is_default else 0
        await self.session.commit()

    async def delete_publisher_config(self, id: str) -> None:
        await self.session.execute(
            delete(PublisherConfigORM).where(PublisherConfigORM.id == id)
        )
        await self.session.commit()

    # --- Cross-table (v0.2 article) ---

    async def get_article(self, article_id: str) -> ArticleORM | None:
        result = await self.session.execute(
            select(ArticleORM).where(ArticleORM.id == article_id)
        )
        return result.scalar_one_or_none()

    # --- PublishJob ---

    async def create_publish_job(
        self,
        article_id: str,
        config_id: str,
        title_override: str | None = None,
    ) -> PublishJobORM:
        job = PublishJobORM(
            id=str(uuid.uuid4()),
            article_id=article_id,
            config_id=config_id,
            title_override=title_override,
            status="pending",
        )
        self.session.add(job)
        await self.session.commit()
        await self.session.refresh(job)
        return job

    async def get_publish_job(self, id: str) -> PublishJobORM | None:
        result = await self.session.execute(
            select(PublishJobORM).where(PublishJobORM.id == id)
        )
        return result.scalar_one_or_none()

    async def list_publish_jobs(
        self, status: str | None = None
    ) -> list[PublishJobORM]:
        stmt = select(PublishJobORM).order_by(PublishJobORM.created_at.desc())
        if status is not None:
            stmt = stmt.where(PublishJobORM.status == status)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def update_publish_job_status(
        self, id: str, status: str, error: str | None = None
    ) -> None:
        job = await self.get_publish_job(id)
        if job is None:
            return
        job.status = status
        if error is not None:
            job.error_message = error
        job.updated_at = datetime.now(timezone.utc)
        await self.session.commit()

    async def update_publish_job_success(
        self, id: str, remote_post_id: int, remote_url: str
    ) -> None:
        job = await self.get_publish_job(id)
        if job is None:
            return
        job.status = "success"
        job.remote_post_id = remote_post_id
        job.remote_url = remote_url
        job.published_at = datetime.now(timezone.utc)
        job.updated_at = datetime.now(timezone.utc)
        await self.session.commit()

    async def count_publish_jobs_by_config(self, config_id: str) -> int:
        result = await self.session.execute(
            select(func.count())
            .select_from(PublishJobORM)
            .where(PublishJobORM.config_id == config_id)
        )
        return result.scalar_one()
