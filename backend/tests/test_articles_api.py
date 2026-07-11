"""Tests for /api/articles/{id} and /api/articles/{id}/download."""
from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.repositories.knowledge_repo import KnowledgeRepository
from app.repositories.task_repo import TaskRepository


@pytest.fixture
async def seeded_article(db_session) -> dict:
    """Create task + article with full content for testing."""
    kb_repo = KnowledgeRepository(db_session)
    task_repo = TaskRepository(db_session)
    kb = await kb_repo.create_kb(name="KB")
    task = await task_repo.create_task(
        name="T", kb_id=kb.id, brand="B", topic="X",
        keywords=[], article_count=1, style="neutral", target_length=500,
    )
    article = await task_repo.create_article(task.id, index=0)
    await task_repo.update_article(
        article.id,
        title="我的真实标题",
        content="# 我的真实标题\n\n这是正文内容。\n\n## 章节 1\n更多内容。",
        content_length=100,
        llm_provider="deepseek",
    )
    # refresh
    refreshed = await task_repo.get_article(article.id)
    return {"article_id": article.id, "title": refreshed.title, "content": refreshed.content}


@pytest.mark.asyncio
async def test_get_article_returns_full_content(seeded_article: dict) -> None:
    """GET /articles/{id} 返回完整 title + content。"""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        r = await client.get(f"/api/articles/{seeded_article['article_id']}")
    assert r.status_code == 200
    data = r.json()
    assert data["title"] == "我的真实标题"
    assert "正文内容" in data["content"]
    assert "## 章节 1" in data["content"]


@pytest.mark.asyncio
async def test_get_article_404(db_session) -> None:
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        r = await client.get("/api/articles/nonexistent-id")
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_download_article_returns_markdown_file(seeded_article: dict) -> None:
    """下载接口返回 text/markdown + Content-Disposition: attachment。"""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        r = await client.get(
            f"/api/articles/{seeded_article['article_id']}/download"
        )
    assert r.status_code == 200
    assert "text/markdown" in r.headers["content-type"]
    assert "charset=utf-8" in r.headers["content-type"].lower()
    cd = r.headers["content-disposition"]
    assert "attachment" in cd
    assert ".md" in cd
    # 文件名包含 sanitized title（CD 头是 URL-encoded，需 url-decode 后比对）
    from urllib.parse import unquote
    decoded_cd = unquote(cd)
    assert "我的真实标题" in decoded_cd
    # body 是原始 Markdown
    body = r.content.decode("utf-8")
    assert body == seeded_article["content"]


@pytest.mark.asyncio
async def test_download_article_sanitizes_unsafe_filename(db_session) -> None:
    """标题含 Windows 非法字符（/\\:*?"<>|）时必须替换。"""
    task_repo = TaskRepository(db_session)
    kb_repo = KnowledgeRepository(db_session)
    kb = await kb_repo.create_kb(name="KB")
    task = await task_repo.create_task(
        name="T", kb_id=kb.id, topic="X", article_count=1, style="neutral",
    )
    article = await task_repo.create_article(task.id, index=0)
    await task_repo.update_article(
        article.id, title='a/b\\c:d*e?f"g<h>i|j',
        content="x",
    )
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        r = await client.get(f"/api/articles/{article.id}/download")
    assert r.status_code == 200
    cd = r.headers["content-disposition"]
    # 不应包含原始非法字符作为文件名
    assert "/" not in cd.split("filename=")[1].split(";")[0]
    assert "\\" not in cd.split("filename=")[1].split(";")[0]
    assert ":" not in cd.split("filename=")[1].split(";")[0]


@pytest.mark.asyncio
async def test_download_article_falls_back_when_no_title(db_session) -> None:
    """title=None 时下载文件名用 'untitled'（不崩）。"""
    task_repo = TaskRepository(db_session)
    kb_repo = KnowledgeRepository(db_session)
    kb = await kb_repo.create_kb(name="KB")
    task = await task_repo.create_task(
        name="T", kb_id=kb.id, topic="X", article_count=1, style="neutral",
    )
    article = await task_repo.create_article(task.id, index=0)
    await task_repo.update_article(article.id, title=None, content="x")
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        r = await client.get(f"/api/articles/{article.id}/download")
    assert r.status_code == 200
    assert ".md" in r.headers["content-disposition"]