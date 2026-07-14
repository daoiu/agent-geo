"""验证 trace_id contextvars 串联（P1#19 / Task 20）。

行为契约：
- new_trace_id() 生成 UUID4 字符串
- set_trace_id(id) 设置当前 contextvar,get_trace_id() 读取
- 不同异步任务 / 不同请求上下文 trace_id 隔离
- trace_id_processor 把 trace_id 注入 structlog 日志记录
- clear_trace_id() 清理 contextvar
"""
from __future__ import annotations

import asyncio
import uuid
from unittest.mock import MagicMock

import pytest
import structlog


def test_new_trace_id_returns_uuid4_string() -> None:
    """new_trace_id 应返回 UUID4 格式字符串。"""
    from app.core.tracing import new_trace_id

    tid = new_trace_id()
    # UUID4 36 字符(含连字符)
    assert len(tid) == 36
    # 反向解析能成 UUID
    parsed = uuid.UUID(tid)
    assert parsed.version == 4


def test_set_and_get_trace_id() -> None:
    """set_trace_id 后 get_trace_id 应返回相同值。"""
    from app.core.tracing import set_trace_id, get_trace_id, clear_trace_id

    clear_trace_id()
    assert get_trace_id() is None

    set_trace_id("test-trace-123")
    assert get_trace_id() == "test-trace-123"
    clear_trace_id()
    assert get_trace_id() is None


def test_trace_id_isolated_across_async_tasks() -> None:
    """不同 asyncio.Task 内的 trace_id 互不影响（contextvars 隔离）。"""
    from app.core.tracing import set_trace_id, get_trace_id, clear_trace_id

    clear_trace_id()

    results: dict[str, str | None] = {}

    async def task_a():
        set_trace_id("task-a-id")
        await asyncio.sleep(0.01)  # 让出执行权
        results["a"] = get_trace_id()

    async def task_b():
        set_trace_id("task-b-id")
        await asyncio.sleep(0.01)
        results["b"] = get_trace_id()

    async def main():
        # 启动两个 task,await 它们完成
        await asyncio.gather(task_a(), task_b())

    asyncio.run(main())

    # 每个 task 内部的 get_trace_id 应是自己设置的值,不是对方的
    assert results["a"] == "task-a-id"
    assert results["b"] == "task-b-id"


def test_trace_id_processor_injects_into_log_record() -> None:
    """trace_id_processor 应从 contextvar 读 trace_id 并注入 log record。"""
    from app.core.tracing import (
        trace_id_processor,
        set_trace_id,
        clear_trace_id,
    )

    clear_trace_id()
    set_trace_id("my-trace-abc")

    # 模拟 structlog 调用 processor
    mock_logger = MagicMock()
    mock_event_dict = {"event": "test_event", "key": "value"}

    result = trace_id_processor(mock_logger, "info", mock_event_dict)

    assert result["trace_id"] == "my-trace-abc", (
        f"trace_id_processor 应注入 trace_id 到 log record,实际 {result}"
    )
    # 原有字段保留
    assert result["event"] == "test_event"
    assert result["key"] == "value"

    clear_trace_id()


def test_trace_id_processor_handles_missing_trace_id() -> None:
    """未设置 trace_id 时,processor 应优雅处理（不抛,字段为 None 或缺失）。"""
    from app.core.tracing import trace_id_processor, clear_trace_id

    clear_trace_id()

    mock_logger = MagicMock()
    result = trace_id_processor(mock_logger, "info", {"event": "x"})

    # 不抛异常,字段为 None 或字段缺失
    assert result.get("trace_id") is None


def test_clear_trace_id_resets_to_none() -> None:
    """clear_trace_id 应重置 contextvar 为 None。"""
    from app.core.tracing import set_trace_id, get_trace_id, clear_trace_id

    set_trace_id("temp")
    assert get_trace_id() == "temp"
    clear_trace_id()
    assert get_trace_id() is None