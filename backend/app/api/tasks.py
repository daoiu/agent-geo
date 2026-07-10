"""Tasks API: create, list, get, delete, cancel."""
from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.diagnosis import get_session
from app.models.orm_v02 import TaskORM
from app.models.task import Article, Task, TaskCreate
from app.repositories.knowledge_repo import KnowledgeRepository
from app.repositories.task_repo import TaskRepository
from app.tasks.task_worker import schedule_task

router = APIRouter(prefix="/tasks", tags=["tasks"])


def _task_to_pydantic(task: TaskORM) -> Task:
    return Task(
        id=task.id,
        name=task.name,
        kb_id=task.kb_id,
        brand=task.brand,
        topic=task.topic,
        keywords=json.loads(task.keywords or "[]"),
        article_count=task.article_count,
        style=task.style,  # type: ignore[arg-type]
        target_length=task.target_length,
        status=task.status,  # type: ignore[arg-type]
        progress=task.progress,
        error_message=task.error_message,
        created_at=task.created_at,
        updated_at=task.updated_at,
    )


@router.post("", status_code=201, response_model=Task)
async def create_task(
    body: TaskCreate,
    session: AsyncSession = Depends(get_session),
) -> Task:
    kb_repo = KnowledgeRepository(session)
    kb = await kb_repo.get_kb(body.kb_id)
    if kb is None:
        raise HTTPException(status_code=404, detail="knowledge base not found")

    task_repo = TaskRepository(session)
    task = await task_repo.create_task(
        name=body.name,
        kb_id=body.kb_id,
        brand=body.brand,
        topic=body.topic,
        keywords=body.keywords,
        article_count=body.article_count,
        style=body.style.value,
        target_length=body.target_length,
    )

    # Schedule background worker
    schedule_task(task.id)

    return _task_to_pydantic(task)


@router.get("", response_model=list[Task])
async def list_tasks(session: AsyncSession = Depends(get_session)) -> list[Task]:
    repo = TaskRepository(session)
    tasks = await repo.list_tasks()
    return [_task_to_pydantic(t) for t in tasks]


@router.get("/{task_id}")
async def get_task(
    task_id: str,
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Task details + list of articles."""
    repo = TaskRepository(session)
    task = await repo.get_task(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="task not found")
    articles = await repo.list_articles(task_id)
    return {
        **_task_to_pydantic(task).model_dump(),
        "articles": [Article.model_validate(a) for a in articles],
    }


@router.delete("/{task_id}", status_code=204, response_class=Response)
async def delete_task(
    task_id: str,
    session: AsyncSession = Depends(get_session),
) -> Response:
    repo = TaskRepository(session)
    task = await repo.get_task(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="task not found")
    if task.status == "running":
        raise HTTPException(
            status_code=409,
            detail="cannot delete running task; cancel it first",
        )
    await repo.delete_task(task_id)
    return Response(status_code=204)


@router.post("/{task_id}/cancel", response_model=Task)
async def cancel_task(
    task_id: str,
    session: AsyncSession = Depends(get_session),
) -> Task:
    """Mark task as cancelled. Worker checks status between articles."""
    repo = TaskRepository(session)
    task = await repo.get_task(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="task not found")
    if task.status in ("completed", "failed", "cancelled"):
        raise HTTPException(
            status_code=409,
            detail=f"task is already {task.status}; cannot cancel",
        )
    await repo.update_task_status(task_id, status="cancelled")
    task = await repo.get_task(task_id)
    return _task_to_pydantic(task)


@router.get("/{task_id}/articles", response_model=list[Article])
async def list_task_articles(
    task_id: str,
    session: AsyncSession = Depends(get_session),
) -> list[Article]:
    repo = TaskRepository(session)
    return await repo.list_articles(task_id)
