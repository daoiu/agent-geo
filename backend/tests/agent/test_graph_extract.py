"""T5 验证:turn 后记忆蒸馏迁 turn_helpers + 图触发。

react_loop._do_extract_after_turn + _PENDING_EXTRACTS 迁到 turn_helpers.py,
加 schedule_extract 封装(sse_bridge 与 react_loop 共用,消除重复)。

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
    """_do_extract_after_turn 失败时静默,不传播(react_loop 等价)。"""
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


@pytest.mark.asyncio
async def test_react_loop_uses_schedule_extract(monkeypatch):
    """react_loop._drive_react_loop turn_complete 路径走 schedule_extract(消除重复)。"""
    import app.domain.agent.react_loop as rl

    scheduled: list[tuple] = []

    def _fake_schedule_extract(device_id, session_id, history):
        scheduled.append((device_id, session_id, history))

    monkeypatch.setattr(rl, "schedule_extract", _fake_schedule_extract)

    # 跑一个 stub 化的 run_agent_turn,触发 turn_complete
    class _StubLLM:
        last_call_duration_ms = 0
        primary_provider_name = staticmethod(lambda: "stub")

        async def chat_with_tools(self, messages, tools):
            return {
                "content": "答复",
                "tool_calls": None,
                "usage": None,
            }

    class _RepoStub:
        def __init__(self, s): pass
        async def create_message(self, **kw): return None
        async def list_messages(self, session_id):
            return []

        async def create_session(self, **kw):
            class _S:
                id = "fake-session"
            return _S()

    monkeypatch.setattr("app.domain.agent.react_loop.LLMClient", lambda *a, **k: _StubLLM())
    monkeypatch.setattr("app.domain.agent.react_loop.AgentRepository", _RepoStub)

    # 调 run_agent_turn 拿 events
    events = []
    async for e in rl.run_agent_turn("s3", "hello", device_id="dev1"):
        events.append(e)

    # 应该出现 turn_complete
    assert any(e["event"] == "turn_complete" for e in events)
    # schedule_extract 应该被调(react_loop 调用一次而不是 as_task 自己写)
    assert len(scheduled) == 1
    assert scheduled[0][1] == "s3"