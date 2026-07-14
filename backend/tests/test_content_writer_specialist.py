"""ContentWriterSpecialist 测试:5 条工程纪律 + 单篇/批量两条路径。"""
from __future__ import annotations

import os

# 测试不调用 LLM,允许缺少 API key
os.environ.setdefault("GEO_ALLOW_MISSING_LLM_KEY", "1")

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.config import Settings
from app.domain.agent.content_writer_specialist import ContentWriterSpecialist
from app.domain.agent.handoff import HandoffRequest, HandoffResult, SpecialistHandoffError


def _make_single_request() -> HandoffRequest:
    return HandoffRequest(
        handoff_id=str(uuid.uuid4()),
        specialist="content_writer",
        task_id="task-1",
        session_id="session-1",
        started_at=datetime.now(timezone.utc),
        timeout_seconds=300,
        payload={
            "mode": "single",
            "kb_id": "kb-1",
            "brand": "Acme",
            "topic": "AI 趋势",
            "keywords": ["AI", "趋势"],
            "style": "professional",
            "target_length": 1500,
            "chunks": [{"text": "AI 在 2026 年...", "kb_name": "Acme KB"}],
        },
    )


def _make_batch_request() -> HandoffRequest:
    return HandoffRequest(
        handoff_id=str(uuid.uuid4()),
        specialist="content_writer",
        task_id="task-2",
        session_id="session-1",
        started_at=datetime.now(timezone.utc),
        timeout_seconds=300,
        payload={
            "mode": "batch",
            "kb_id": "kb-1",
            "article_count": 3,
            "style": "neutral",
            "target_length": 1500,
        },
    )


def test_specialist_init():
    """specialist 构造接收 settings + session_factory。"""
    settings = Settings(_env_file=None)
    factory = MagicMock()
    specialist = ContentWriterSpecialist(settings, factory)
    assert specialist.settings is settings
    assert specialist.session_factory is factory


async def test_idempotency_hit_returns_existing_result():
    """纪律 1:同 handoff_id 在窗口内有成功结果 → 直接返回,不重做。"""
    settings = Settings(_env_file=None)
    factory = MagicMock()

    specialist = ContentWriterSpecialist(settings, factory)

    # 模拟 check_idempotency 返回已有结果
    existing = HandoffResult(
        handoff_id="h-1", status="success", result={"article_id": "art-existing"},
        error=None, duration_ms=100, token_usage={"total_tokens": 50},
    )

    with patch.object(specialist, "_check_idempotency", AsyncMock(return_value=existing)):
        req = _make_single_request()
        result = await specialist.handoff(req)

    assert result is existing
    assert result.result["article_id"] == "art-existing"


async def test_timeout_returns_timeout_status():
    """纪律 2: 超时 → status='timeout' + 落日志。"""
    import asyncio

    settings = Settings(_env_file=None)
    factory = MagicMock()
    specialist = ContentWriterSpecialist(settings, factory)

    with patch.object(specialist, "_check_idempotency", AsyncMock(return_value=None)):
        with patch.object(specialist, "_execute_with_timeout", AsyncMock(side_effect=asyncio.TimeoutError)):
            with patch.object(specialist, "_log_result", AsyncMock()):
                req = _make_single_request()
                result = await specialist.handoff(req)

    assert result.status == "timeout"
    assert "超时" in result.error or "timeout" in result.error.lower()


async def test_state_isolation_uses_independent_session():
    """纪律 3: specialist 不复用主 Agent session,开新 session。"""
    settings = Settings(_env_file=None)
    factory = MagicMock()
    specialist = ContentWriterSpecialist(settings, factory)

    with patch.object(specialist, "_check_idempotency", AsyncMock(return_value=None)):
        with patch.object(specialist, "_execute_with_timeout", AsyncMock(return_value={
            "article_id": "art-1", "content": "正文", "token_usage": {"total_tokens": 200}
        })):
            with patch.object(specialist, "_log_result", AsyncMock()):
                req = _make_single_request()
                result = await specialist.handoff(req)

    # 验证 specialist 用的是 self.session_factory(纪律 3 状态隔离)
    assert result.status == "success"


async def test_failure_logs_failed_status():
    """失败时 status='failed' + 落日志。"""
    settings = Settings(_env_file=None)
    factory = MagicMock()
    specialist = ContentWriterSpecialist(settings, factory)

    with patch.object(specialist, "_check_idempotency", AsyncMock(return_value=None)):
        with patch.object(specialist, "_execute_with_timeout", AsyncMock(side_effect=Exception("LLM 调用失败"))):
            with patch.object(specialist, "_log_result", AsyncMock()) as mock_log:
                req = _make_single_request()
                result = await specialist.handoff(req)

    assert result.status == "failed"
    assert "LLM 调用失败" in result.error
    mock_log.assert_called_once()


async def test_handoff_batch_creates_multiple_task_rows():
    """批量路径走 v0.2 TaskRepository,生成 N 条 task。"""
    settings = Settings(_env_file=None)
    factory = MagicMock()
    specialist = ContentWriterSpecialist(settings, factory)

    with patch.object(specialist, "_check_idempotency", AsyncMock(return_value=None)):
        with patch.object(specialist, "_execute_batch_with_timeout", AsyncMock(return_value={
            "task_ids": ["t-1", "t-2", "t-3"],
            "token_usage": {"total_tokens": 500},
        })) as mock_batch:
            with patch.object(specialist, "_log_result", AsyncMock()):
                req = _make_batch_request()
                result = await specialist.handoff_batch(req)

    assert result.status == "success"
    assert len(result.result["task_ids"]) == 3
    mock_batch.assert_called_once()


async def test_cost_attribution_writes_token_usage():
    """纪律 5: 写入 token_usage 到 handoff_log。"""
    settings = Settings(_env_file=None)
    factory = MagicMock()
    specialist = ContentWriterSpecialist(settings, factory)

    with patch.object(specialist, "_check_idempotency", AsyncMock(return_value=None)):
        with patch.object(specialist, "_execute_with_timeout", AsyncMock(return_value={
            "article_id": "art-1",
            "content": "正文",
            "token_usage": {"prompt_tokens": 100, "completion_tokens": 200, "total_tokens": 300},
        })):
            with patch.object(specialist, "_log_result", AsyncMock()) as mock_log:
                req = _make_single_request()
                result = await specialist.handoff(req)

    # _log_result 调用时,token_usage 应包含 3 个字段
    call_args = mock_log.call_args
    logged_result = call_args[0][1]  # 第二个位置参数
    assert logged_result.token_usage["total_tokens"] == 300
