"""Tests for create_generation_task executor (v0.6 P1.4)."""
from __future__ import annotations

from unittest.mock import patch

import pytest

from app.domain.agent.tool_executor import ToolExecutor
from app.domain.agent.tools import CreateGenerationTaskArgs


@pytest.mark.asyncio
async def test_create_generation_task_happy_path(db_session):
    """正常路径 → 调 TaskRepository.create_task + schedule_task → 返 task_id."""
    from app.repositories.task_repo import TaskRepository
    from app.repositories.knowledge_repo import KnowledgeRepository

    repo = KnowledgeRepository(db_session)
    kb = await repo.create_kb(name="KB")
    await db_session.commit()

    executor = ToolExecutor(session_id="s1")
    args = CreateGenerationTaskArgs(
        kb_id=kb.id,
        brand="北北云吞",
        topic="玉林老字号云吞店介绍",
        article_count=5,
        keywords=["云吞", "皮薄", "马蹄"],
        style="professional",
    )

    with patch.object(TaskRepository, "create_task") as MockCreate, \
         patch("app.domain.agent.tool_executor.schedule_task") as MockSched:
        # 模拟真实 repo 返回带 id 的 task
        MockCreate.return_value = type("T", (), {
            "id": "task-fake-123",
            "status": "pending",
            "article_count": 5,
        })()
        result = await executor._execute_create_generation_task(args)

    MockCreate.assert_called_once()
    call_kwargs = MockCreate.call_args.kwargs
    assert call_kwargs["kb_id"] == kb.id
    assert call_kwargs["brand"] == "北北云吞"
    assert call_kwargs["article_count"] == 5

    MockSched.assert_called_once_with("task-fake-123")

    assert result["task_id"] == "task-fake-123"
    assert result["status"] == "pending"
    assert result["article_count"] == 5
    assert "/tasks/task-fake-123" in result["next_step"]


@pytest.mark.asyncio
async def test_create_generation_task_unknown_kb_returns_404(db_session):
    """kb_id 不存在时返 404-like error，不抛 HumanConfirmation."""
    executor = ToolExecutor(session_id="s1")
    args = CreateGenerationTaskArgs(
        kb_id="bogus-kb-id",
        brand="X",
        topic="足够长的 topic 内容",
        article_count=1,
        keywords=["x"],
    )

    with pytest.raises(Exception) as excinfo:  # ValueError（KB 不存在）
        await executor._execute_create_generation_task(args)
    # 不应该是 HumanConfirmationRequired
    from app.domain.exceptions import HumanConfirmationRequired
    assert not isinstance(excinfo.value, HumanConfirmationRequired)
