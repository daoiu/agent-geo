"""Publisher API: WordPress credentials + publish jobs."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.diagnosis import get_session
from app.domain.publisher.publisher_service import PublishService
from app.domain.security.encryption import encrypt
from app.models.publisher import (
    PublishJob,
    PublishJobCreate,
    PublisherConfig,
    PublisherConfigCreate,
    PublisherConfigUpdate,
)
from app.repositories.publisher_repo import PublishRepository

# Two routers because prefixes differ
configs_router = APIRouter(prefix="/publishers", tags=["publishers"])
jobs_router = APIRouter(prefix="/publishes", tags=["publishes"])


# --- PublisherConfig endpoints ---

@configs_router.post("", status_code=201, response_model=PublisherConfig)
async def create_publisher_config(
    body: PublisherConfigCreate,
    session: AsyncSession = Depends(get_session),
) -> PublisherConfig:
    repo = PublishRepository(session)
    encrypted = encrypt(body.app_password)
    return await repo.create_publisher_config(
        name=body.name,
        site_url=str(body.site_url),
        username=body.username,
        app_password_encrypted=encrypted,
    )


@configs_router.get("", response_model=list[PublisherConfig])
async def list_publisher_configs(
    session: AsyncSession = Depends(get_session),
) -> list[PublisherConfig]:
    repo = PublishRepository(session)
    return await repo.list_publisher_configs()


@configs_router.get("/{pc_id}", response_model=PublisherConfig)
async def get_publisher_config(
    pc_id: str,
    session: AsyncSession = Depends(get_session),
) -> PublisherConfig:
    repo = PublishRepository(session)
    pc = await repo.get_publisher_config(pc_id)
    if pc is None:
        raise HTTPException(status_code=404, detail="publisher config not found")
    return pc


@configs_router.put("/{pc_id}", response_model=PublisherConfig)
async def update_publisher_config(
    pc_id: str,
    body: PublisherConfigUpdate,
    session: AsyncSession = Depends(get_session),
) -> PublisherConfig:
    """Update mutable fields. app_password is optional — if provided, re-encrypt."""
    repo = PublishRepository(session)
    kwargs: dict = {}
    if body.name is not None:
        kwargs["name"] = body.name
    if body.site_url is not None:
        kwargs["site_url"] = str(body.site_url)
    if body.username is not None:
        kwargs["username"] = body.username
    if body.is_default is not None:
        kwargs["is_default"] = body.is_default
    if body.app_password is not None:
        kwargs["app_password_encrypted"] = encrypt(body.app_password)
    await repo.update_publisher_config(pc_id, **kwargs)
    pc = await repo.get_publisher_config(pc_id)
    if pc is None:
        raise HTTPException(status_code=404, detail="publisher config not found")
    return pc


@configs_router.delete("/{pc_id}", status_code=204)
async def delete_publisher_config(
    pc_id: str,
    session: AsyncSession = Depends(get_session),
) -> Response:
    repo = PublishRepository(session)
    count = await repo.count_publish_jobs_by_config(pc_id)
    if count > 0:
        raise HTTPException(
            status_code=409,
            detail=f"cannot delete: {count} publish job(s) reference this config",
        )
    pc = await repo.get_publisher_config(pc_id)
    if pc is None:
        raise HTTPException(status_code=404, detail="publisher config not found")
    await repo.delete_publisher_config(pc_id)
    return Response(status_code=204)


@configs_router.post("/{pc_id}/test")
async def test_publisher_config(
    pc_id: str,
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Test connection: decrypt creds + call /users/me."""
    from app.domain.publisher.wordpress import WordPressClient
    from app.domain.security.encryption import decrypt

    repo = PublishRepository(session)
    pc = await repo.get_publisher_config(pc_id)
    if pc is None:
        raise HTTPException(status_code=404, detail="publisher config not found")
    try:
        pw = decrypt(pc.app_password_encrypted)
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"decrypt failed: {e}")

    client = WordPressClient(
        site_url=pc.site_url, username=pc.username, app_password=pw
    )
    try:
        info = await client.test_connection()
        return {"ok": True, "user": info}
    finally:
        await client.close()


# --- PublishJob endpoints ---

@jobs_router.post("", status_code=201, response_model=PublishJob)
async def create_publish_job(
    body: PublishJobCreate,
    session: AsyncSession = Depends(get_session),
) -> PublishJob:
    """Create publish job. Article MUST be approved."""
    from sqlalchemy import select
    from app.models.orm_v02 import ArticleORM

    # Validate article approved
    result = await session.execute(
        select(ArticleORM).where(ArticleORM.id == body.article_id)
    )
    article = result.scalar_one_or_none()
    if article is None:
        raise HTTPException(status_code=404, detail="article not found")
    if article.review_status != "approved":
        raise HTTPException(
            status_code=422,
            detail=f"article must be approved (current: {article.review_status})",
        )

    # Validate config exists
    repo = PublishRepository(session)
    pc = await repo.get_publisher_config(body.config_id)
    if pc is None:
        raise HTTPException(status_code=404, detail="publisher config not found")

    job = await repo.create_publish_job(
        article_id=body.article_id,
        config_id=body.config_id,
        title_override=body.title_override,
    )

    # Schedule worker (T2.3)
    from app.tasks import publish_worker
    publish_worker.schedule_publish(job.id)
    return job


@jobs_router.get("", response_model=list[PublishJob])
async def list_publish_jobs(
    status: str | None = None,
    session: AsyncSession = Depends(get_session),
) -> list[PublishJob]:
    repo = PublishRepository(session)
    return await repo.list_publish_jobs(status=status)


@jobs_router.get("/{job_id}", response_model=PublishJob)
async def get_publish_job(
    job_id: str,
    session: AsyncSession = Depends(get_session),
) -> PublishJob:
    repo = PublishRepository(session)
    job = await repo.get_publish_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="publish job not found")
    return job


@jobs_router.post("/{job_id}/retry", response_model=PublishJob)
async def retry_publish_job(
    job_id: str,
    session: AsyncSession = Depends(get_session),
) -> PublishJob:
    """Retry a failed job. Reset to pending and reschedule."""
    repo = PublishRepository(session)
    job = await repo.get_publish_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="publish job not found")
    if job.status != "failed":
        raise HTTPException(
            status_code=409,
            detail=f"only failed jobs can be retried (current: {job.status})",
        )
    await repo.update_publish_job_status(job_id, status="pending", error=None)
    from app.tasks import publish_worker
    publish_worker.schedule_publish(job_id)
    job = await repo.get_publish_job(job_id)
    return job


@jobs_router.post("/{job_id}/cancel", response_model=PublishJob)
async def cancel_publish_job(
    job_id: str,
    session: AsyncSession = Depends(get_session),
) -> PublishJob:
    repo = PublishRepository(session)
    job = await repo.get_publish_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="publish job not found")
    if job.status not in ("pending", "running"):
        raise HTTPException(
            status_code=409,
            detail=f"cannot cancel job in status {job.status}",
        )
    await repo.update_publish_job_status(job_id, status="cancelled")
    job = await repo.get_publish_job(job_id)
    return job
