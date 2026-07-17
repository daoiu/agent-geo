"""T5 验证:turn 后记忆蒸馏迁 turn_helpers + 图触发。

schedule_extract 封装从 turn_helpers 模块导出,sse_bridge 与 react_graph
共用(react_loop 已删,plan Task 10)。

调度契约:fire-and-forget,不阻塞 turn;失败静默,不阻塞主流程。
"""
from __future__ import annotations

import asyncio

import pytest


@pytest.mark.asyncio
async def test_schedule_extract_fires_and_forget(monkeypatch):
    """schedule_extract 异步触发 _do_extract_after_turn,不阻塞调用方。"""
    from app.domain.agent import turn_helpers as th

    called = {}

    async def _fake_extract(device_id, session_id, history):
        called["hit"] = session_id
        called["device_id"] = device_id

    monkeypatch.setattr(th, "_do_extract_after_turn", _fake_extract)

    th.schedule_extract(None, "s1", [{"role": "user", "content": "q"}])
    # 给 task 一点时间跑
    await asyncio.sleep(0.05)
    assert called.get("hit") == "s1"
    assert called.get("device_id") is None


@pytest.mark.asyncio
async def test_schedule_extract_swallows_errors(monkeypatch):
    """_do_extract_after_turn 失败时静默,不传播。"""
    from app.domain.agent import turn_helpers as th

    async def _fake_extract_boom(device_id, session_id, history):
        raise RuntimeError("db down")

    monkeypatch.setattr(th, "_do_extract_after_turn", _fake_extract_boom)

    # 不应抛异常
    th.schedule_extract("dev1", "s2", [{"role": "user", "content": "x"}])
    # 给 task 一点时间
    await asyncio.sleep(0.05)
    # schedule_extract 本身立即返回(不阻塞);后台 task 失败静默,不传播
    assert True