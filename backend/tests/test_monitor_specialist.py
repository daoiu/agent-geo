"""MonitorSpecialist 测试:5 条纪律 + 派生 handoff_id。"""
from __future__ import annotations

import os

# 测试不调用 LLM,允许缺少 API key
os.environ.setdefault("GEO_ALLOW_MISSING_LLM_KEY", "1")

import asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.config import Settings
from app.domain.agent.handoff import HandoffResult
from app.domain.monitor.monitor_specialist import MonitorSpecialist


async def test_handoff_id_derivation_uses_iso_timestamp():
    """派生规则: monitor-{task_id}-{iso ts},同 task 不同时刻是独立执行。"""
    settings = Settings(_env_file=None)
    factory = MagicMock()
    specialist = MonitorSpecialist(settings, factory)

    ts1 = datetime(2026, 7, 14, 10, 0, 0, tzinfo=timezone.utc)
    ts2 = datetime(2026, 7, 14, 14, 0, 0, tzinfo=timezone.utc)
    id1 = specialist._derive_handoff_id("task-1", ts1)
    id2 = specialist._derive_handoff_id("task-1", ts2)
    assert id1 != id2
    assert id1 == "monitor-task-1-2026-07-14T10:00:00+00:00"


async def test_idempotency_within_window_returns_existing():
    """纪律 1: 24h 窗口内同 handoff_id 命中 → 返回已有结果。"""
    settings = Settings(_env_file=None)
    factory = MagicMock()
    specialist = MonitorSpecialist(settings, factory)

    existing = HandoffResult(
        handoff_id="h-1", status="success",
        result={"mention_rate": 0.5}, error=None,
        duration_ms=100, token_usage={"total_tokens": 50},
    )

    with patch.object(specialist, "_check_idempotency", AsyncMock(return_value=existing)):
        result = await specialist.run("task-1")

    assert result is existing


async def test_timeout_returns_timeout_status():
    """纪律 2: monitor 默认 60s 超时。"""
    settings = Settings(_env_file=None)
    factory = MagicMock()
    specialist = MonitorSpecialist(settings, factory)

    with patch.object(specialist, "_check_idempotency", AsyncMock(return_value=None)):
        with patch.object(specialist, "_execute_with_timeout", AsyncMock(side_effect=asyncio.TimeoutError)):
            with patch.object(specialist, "_log_result", AsyncMock()):
                result = await specialist.run("task-1")

    assert result.status == "timeout"


async def test_failure_falls_back_to_legacy_service():
    """纪律 4: monitor 失败时降级到 MonitorService.execute_monitor_run(transient 异常被 catch)。"""
    import httpx

    settings = Settings(_env_file=None)
    factory = MagicMock()
    specialist = MonitorSpecialist(settings, factory)

    with patch.object(specialist, "_check_idempotency", AsyncMock(return_value=None)):
        # httpx.HTTPError 在 _LLM_TRANSIENT_EXCEPTIONS 中,触发 catch (走 failed + 降级)
        # 注:asyncio.TimeoutError 会被外层 except 捕获为 timeout,不会触发降级
        with patch.object(specialist, "_execute_with_timeout", AsyncMock(side_effect=httpx.HTTPError("LLM 失败"))):
            with patch.object(specialist, "_log_result", AsyncMock()):
                with patch("app.domain.monitor.monitor_specialist.execute_monitor_run", new=AsyncMock(return_value=None)) as mock_legacy:
                    result = await specialist.run("task-1")

    # 降级到旧路径,返回 failed 状态但 legacy 被调
    assert result.status == "failed"
    mock_legacy.assert_called_once()


async def test_cost_attribution_writes_token_usage():
    """纪律 5: monitor token 用量写入 handoff_log。"""
    settings = Settings(_env_file=None)
    factory = MagicMock()
    specialist = MonitorSpecialist(settings, factory)

    with patch.object(specialist, "_check_idempotency", AsyncMock(return_value=None)):
        with patch.object(specialist, "_execute_with_timeout", AsyncMock(return_value={
            "mention_rate": 0.5,
            "token_usage": {"prompt_tokens": 200, "completion_tokens": 100, "total_tokens": 300},
        })):
            with patch.object(specialist, "_log_result", AsyncMock()) as mock_log:
                result = await specialist.run("task-1")

    call_args = mock_log.call_args
    logged_result = call_args[0][1]
    assert logged_result.token_usage["total_tokens"] == 300
