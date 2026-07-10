"""Reviews API: list review queue, approve / reject / revise articles."""
from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.diagnosis import get_session
from app.models.task import Article, ReviewAction
from app.repositories.task_repo import TaskRepository

router = APIRouter(prefix="/reviews", tags=["reviews"])


def _article_to_pydantic(article) -> Article:
    """Convert ORM article → Pydantic Article (parses cited_chunks JSON)."""
    cited = json.loads(article.cited_chunks or "[]")
    return Article(
        id=article.id,
        task_id=article.task_id,
        title=article.title,
        content=article.content,
        content_length=article.content_length,
        review_status=article.review_status,  # type: ignore[arg-type]
        review_note=article.review_note,
        reviewed_at=article.reviewed_at,
        cited_chunks=cited,
        llm_provider=article.llm_provider,
        error_message=article.error_message,
        created_at=article.created_at,
        updated_at=article.updated_at,
    )


@router.get("", response_model=list[Article])
async def list_reviews(
    status: str = "pending",
    task_id: str | None = None,
    session: AsyncSession = Depends(get_session),
) -> list[Article]:
    repo = TaskRepository(session)
    rows = await repo.list_articles_by_status(status, task_id=task_id)
    return [_article_to_pydantic(a) for a in rows]


@router.get("/{article_id}", response_model=Article)
async def get_article(
    article_id: str,
    session: AsyncSession = Depends(get_session),
) -> Article:
    repo = TaskRepository(session)
    article = await repo.get_article(article_id)
    if article is None:
        raise HTTPException(status_code=404, detail="article not found")
    return _article_to_pydantic(article)


@router.post("/{article_id}/approve", response_model=Article)
async def approve_article(
    article_id: str,
    body: ReviewAction = ReviewAction(),
    session: AsyncSession = Depends(get_session),
) -> Article:
    repo = TaskRepository(session)
    article = await repo.get_article(article_id)
    if article is None:
        raise HTTPException(status_code=404, detail="article not found")
    if article.review_status != "pending":
        raise HTTPException(
            status_code=409,
            detail=f"article is already {article.review_status}",
        )
    await repo.update_article_review(
        article_id, status="approved", note=body.note
    )
    article = await repo.get_article(article_id)
    return _article_to_pydantic(article)


@router.post("/{article_id}/reject", response_model=Article)
async def reject_article(
    article_id: str,
    body: ReviewAction,
    session: AsyncSession = Depends(get_session),
) -> Article:
    if not body.note or not body.note.strip():
        raise HTTPException(
            status_code=422,
            detail="reject requires a non-empty note explaining the reason",
        )
    repo = TaskRepository(session)
    article = await repo.get_article(article_id)
    if article is None:
        raise HTTPException(status_code=404, detail="article not found")
    if article.review_status != "pending":
        raise HTTPException(
            status_code=409,
            detail=f"article is already {article.review_status}",
        )
    await repo.update_article_review(
        article_id, status="rejected", note=body.note
    )
    article = await repo.get_article(article_id)
    return _article_to_pydantic(article)


@router.post("/{article_id}/revise", response_model=Article)
async def request_revision(
    article_id: str,
    body: ReviewAction,
    session: AsyncSession = Depends(get_session),
) -> Article:
    """Mark article as needing revision. v0.2 only flags it; does not regenerate."""
    if not body.note or not body.note.strip():
        raise HTTPException(
            status_code=422,
            detail="revise requires a note describing what to change",
        )
    repo = TaskRepository(session)
    article = await repo.get_article(article_id)
    if article is None:
        raise HTTPException(status_code=404, detail="article not found")
    await repo.update_article_review(
        article_id, status="revise_requested", note=body.note
    )
    article = await repo.get_article(article_id)
    return _article_to_pydantic(article)
