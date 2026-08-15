"""ToolExecutor 接入 specialist 测试:纪律 4 失败回退。"""
from __future__ import annotations

import os

# 测试不调用 LLM,允许缺少 API key
os.environ.setdefault("GEO_ALLOW_MISSING_LLM_KEY", "1")

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.domain.agent.handoff import HandoffResult
from app.domain.agent.tool_executor import ToolExecutor
from app.domain.agent.tools import CreateGenerationTaskArgs, GenerateArticleArgs


def _successful_specialist_result(handoff_id: str) -> HandoffResult:
    return HandoffResult(
        handoff_id=handoff_id,
        status="success",
        result={"task_id": "task-specialist", "kb_id": "kb-1", "article_count": 1},
        error=None,
        duration_ms=1500,
        token_usage={"prompt_tokens": 100, "completion_tokens": 200, "total_tokens": 300},
    )


def _failed_specialist_result(handoff_id: str) -> HandoffResult:
    return HandoffResult(
        handoff_id=handoff_id,
        status="failed",
        result=None,
        error="specialist 失败",
        duration_ms=500,
        token_usage={},
    )


async def test_generate_article_uses_specialist():
    """generate_article 走 specialist handoff。"""
    executor = ToolExecutor(session_id="session-1")
    args = GenerateArticleArgs(
        kb_id="kb-1", brand="Acme", topic="AI 趋势分析",
        keywords=["AI", "趋势"], style="professional", target_length=1500,
    )

    with patch.object(executor, "_get_specialist") as mock_get_spec:
        mock_specialist = MagicMock()
        mock_specialist.handoff = AsyncMock(return_value=_successful_specialist_result("h-1"))
        mock_get_spec.return_value = mock_specialist

        result = await executor.execute("generate_article", args.model_dump())

    assert "task_id" in result
    assert result["task_id"] == "task-specialist"
    mock_specialist.handoff.assert_called_once()
    call_args = mock_specialist.handoff.call_args
    req = call_args[0][0]
    assert req.specialist == "content_writer"
    assert req.payload["brand"] == "Acme"


async def test_create_generation_task_uses_specialist_batch():
    """create_generation_task 走 specialist handoff_batch。"""
    executor = ToolExecutor(session_id="session-1")
    args = CreateGenerationTaskArgs(
        kb_id="kb-1", brand="Acme", topic="批量趋势文章",
        keywords=["趋势", "AI"], article_count=3, style="neutral", target_length=1500,
    )

    with patch.object(executor, "_get_specialist") as mock_get_spec:
        mock_specialist = MagicMock()
        mock_specialist.handoff_batch = AsyncMock(return_value=HandoffResult(
            handoff_id="h-2", status="success",
            result={"task_ids": ["t-1", "t-2", "t-3"]},
            error=None, duration_ms=2000, token_usage={"total_tokens": 500},
        ))
        mock_get_spec.return_value = mock_specialist

        result = await executor.execute("create_generation_task", args.model_dump())

    assert "task_ids" in result
    assert len(result["task_ids"]) == 3


async def test_specialist_failure_falls_back_to_legacy_path():
    """纪律 4: specialist 失败时降级到旧路径(_execute_generate_article_legacy)。"""
    executor = ToolExecutor(session_id="session-1")
    args = GenerateArticleArgs(
        kb_id="kb-1", brand="Acme", topic="AI 趋势分析",
        keywords=["AI", "趋势"], style="professional", target_length=1500,
    )

    with patch.object(executor, "_get_specialist") as mock_get_spec:
        mock_specialist = MagicMock()
        mock_specialist.handoff = AsyncMock(return_value=_failed_specialist_result("h-1"))
        mock_get_spec.return_value = mock_specialist

        with patch.object(executor, "_execute_generate_article_legacy", AsyncMock(return_value={
            "task_id": "task-legacy",
            "kb_id": "kb-1",
            "article_count": 1,
            "status": "pending",
            "next_step": "降级到旧路径",
        })) as mock_legacy:
            result = await executor.execute("generate_article", args.model_dump())

    assert result["task_id"] == "task-legacy"
    mock_legacy.assert_called_once()
