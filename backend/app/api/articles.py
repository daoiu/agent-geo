"""Articles API: 单篇详情 + Markdown 下载。

为什么独立路由：articles 是 article 维度资源，不是 task 子资源。
详情页 + 一键下载 .md 文件都应该直接 GET /articles/{id}。
"""
from __future__ import annotations

import re
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.diagnosis import get_session
from app.models.task import Article
from app.repositories.task_repo import TaskRepository

router = APIRouter(prefix="/articles", tags=["articles"])


@router.get("/{article_id}", response_model=Article)
async def get_article(
    article_id: str,
    session: AsyncSession = Depends(get_session),
) -> Article:
    """单篇详情（含完整 title + content）。"""
    repo = TaskRepository(session)
    article = await repo.get_article(article_id)
    if article is None:
        raise HTTPException(status_code=404, detail="article not found")
    return Article.from_orm_obj(article)


@router.get("/{article_id}/download")
async def download_article_markdown(
    article_id: str,
    session: AsyncSession = Depends(get_session),
) -> Response:
    """下载完整 Markdown 文件。

    - 文件名：{article_id}-{sanitized_title}.md
    - Content-Type: text/markdown; charset=utf-8
    - Content-Disposition: attachment（强制下载）
    """
    repo = TaskRepository(session)
    article = await repo.get_article(article_id)
    if article is None:
        raise HTTPException(status_code=404, detail="article not found")

    title = article.title or "未命名文章"
    safe_title = _sanitize_filename(title)
    filename = f"{article_id[:8]}-{safe_title}.md"

    body = article.content or ""
    # RFC 5987: 中文文件名 UTF-8 编码
    return Response(
        content=body,
        media_type="text/markdown; charset=utf-8",
        headers={
            "Content-Disposition": (
                f"attachment; filename={quote(filename, safe='')}; "
                f"filename*=UTF-8''{quote(filename)}"
            ),
        },
    )


def _sanitize_filename(name: str) -> str:
    """去除文件名非法字符（Windows + Unix）。"""
    s = re.sub(r'[\\/:*?"<>|\r\n\t]', "_", name)
    s = s.strip().strip(".")
    return s[:60] or "untitled"