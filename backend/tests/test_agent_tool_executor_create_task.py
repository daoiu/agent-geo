"""Tests for create_generation_task executor (v0.6+ Multi-Agent).

新架构: create_generation_task 先走 ContentWriterSpecialist.handoff_batch,
成功直接返回 task_ids;失败/超时降级到 legacy 路径(TaskRepository + schedule_task)。
specialist 主路径的 mock 形状见 test_tool_executor_specialist_integration.py。
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.domain.agent.handoff import HandoffResult
from app.domain.agent.tool_executor import ToolExecutor
from app.domain.agent.tools import CreateGenerationTaskArgs


@pytest.mark.asyncio
async def test_create_generation_task_happy_path(db_session):
    """正常路径 → specialist handoff_batch 成功 → 返 task_ids(不调 schedule_task)."""
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

    with patch.object(executor, "_get_specialist") as mock_get_spec:
        mock_specialist = MagicMock()
        mock_specialist.handoff_batch = AsyncMock(return_value=HandoffResult(
            handoff_id="h-1",
            status="success",
            result={"task_ids": ["task-spec-123"]},
            error=None,
            duration_ms=100,
            token_usage={},
        ))
        mock_get_spec.return_value = mock_specialist

        with patch("app.domain.agent.tool_executor.schedule_task") as MockSched:
            result = await executor._execute_create_generation_task(args)

    mock_specialist.handoff_batch.assert_called_once()
    call_req = mock_specialist.handoff_batch.call_args[0][0]
    call_kwargs = call_req.payload
    assert call_kwargs["kb_id"] == kb.id
    assert call_kwargs["brand"] == "北北云吞"
    assert call_kwargs["article_count"] == 5
    assert call_req.specialist == "content_writer"

    # specialist 成功路径不创建后台任务
    MockSched.assert_not_called()

    assert result["task_ids"] == ["task-spec-123"]


@pytest.mark.asyncio
async def test_create_generation_task_specialist_failure_falls_back(db_session):
    """specialist 失败 → 降级 legacy: create_task + schedule_task + 返 task_id."""
    from app.repositories.knowledge_repo import KnowledgeRepository
    from app.repositories.task_repo import TaskRepository

    repo = KnowledgeRepository(db_session)
    kb = await repo.create_kb(name="KB")
    await db_session.commit()

    executor = ToolExecutor(session_id="s1")
    args = CreateGenerationTaskArgs(
        kb_id=kb.id,
        brand="北北云吞",
        topic="玉林老字号云吞店介绍",
        article_count=2,
        keywords=["云吞"],
        style="professional",
    )

    with patch.object(executor, "_get_specialist") as mock_get_spec:
        mock_specialist = MagicMock()
        mock_specialist.handoff_batch = AsyncMock(return_value=HandoffResult(
            handoff_id="h-1",
            status="failed",
            result=None,
            error="specialist 失败",
            duration_ms=100,
            token_usage={},
        ))
        mock_get_spec.return_value = mock_specialist

        with patch("app.domain.agent.tool_executor.schedule_task") as MockSched:
            result = await executor._execute_create_generation_task(args)

    MockSched.assert_called_once_with(result["task_id"])
    assert result["task_id"] != "task-spec-123"
    assert "审核" in result["next_step"]

    # legacy 真实落库验证
    task_repo = TaskRepository(db_session)
    task = await task_repo.get_task(result["task_id"])
    assert task is not None
    assert task.brand == "北北云吞"
    assert task.article_count == 2


@pytest.mark.asyncio
async def test_create_generation_task_unknown_kb_returns_404(db_session):
    """kb_id 不存在时(legacy 降级路径检查 KB)抛 ValueError,不抛 HumanConfirmation."""
    executor = ToolExecutor(session_id="s1")
    args = CreateGenerationTaskArgs(
        kb_id="bogus-kb-id",
        brand="X",
        topic="足够长的 topic 内容",
        article_count=1,
        keywords=["x"],
    )

    from app.domain.exceptions import HumanConfirmationRequired

    with patch.object(executor, "_get_specialist") as mock_get_spec:
        mock_specialist = MagicMock()
        mock_specialist.handoff_batch = AsyncMock(return_value=HandoffResult(
            handoff_id="h-1",
            status="failed",
            result=None,
            error="specialist 失败",
            duration_ms=100,
            token_usage={},
        ))
        mock_get_spec.return_value = mock_specialist

        with pytest.raises(ValueError) as excinfo:
            await executor._execute_create_generation_task(args)

    # 不应该是 HumanConfirmationRequired
    assert not isinstance(excinfo.value, HumanConfirmationRequired)
