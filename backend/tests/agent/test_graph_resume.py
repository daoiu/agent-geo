"""T7 验证:HITL generate_article 确认续跑迁到图 resume。

react_loop.run_agent_turn_from_checkpoint(L596+)迁到
langgraph_nodes/resume.py:resume_from_checkpoint(session_id, checkpoint_message_id,
device_id=None) -> AsyncIterator[dict],用 LangGraph Command(resume=...) +
graph.astream_events 续跑,经 SSEBridge._dispatch 产出 dict 流(agent_chat 层
统一 SSE 包装)。

测试焦点:
- 缺失/已 resolved checkpoint message → yield error 事件后退出
- 不抛异常,可迭代产出 dict
"""
from __future__ import annotations

from contextlib import asynccontextmanager

import pytest


class _FakeFactory:
    """最小 fake factory:`async with f() as session` 产出任意占位。"""

    def __call__(self):
        return _FakeSessionCtx()


class _FakeSessionCtx:
    async def __aenter__(self):
        return object()

    async def __aexit__(self, *a):
        return False


@pytest.mark.asyncio
async def test_resume_missing_checkpoint_yields_error(monkeypatch):
    """checkpoint message 不存在 → resume_from_checkpoint 立即 yield error 事件。"""
    from app.domain.agent.langgraph_nodes import resume

    class _RepoMissing:
        def __init__(self, s): pass
        async def get_message(self, mid): return None

    monkeypatch.setattr(resume, "AgentRepository", _RepoMissing)
    monkeypatch.setattr(resume, "get_session_factory", lambda: _FakeFactory())

    outs = []
    async for evt in resume.resume_from_checkpoint("s1", "missing-id"):
        outs.append(evt)

    assert outs, "expected at least one SSE dict"
    assert outs[0]["event"] == "error"
    assert "missing-id" in outs[0]["message"] or "not found" in outs[0]["message"]


@pytest.mark.asyncio
async def test_resume_already_resolved_yields_error(monkeypatch):
    """checkpoint 已 resolved(pending_confirmation=False)→ yield error。"""
    from app.domain.agent.langgraph_nodes import resume

    class _AlreadyResolved:
        id = "ckpt1"
        session_id = "s1"
        pending_confirmation = False
        tool_calls = None

    class _Repo:
        def __init__(self, s): pass
        async def get_message(self, mid): return _AlreadyResolved()

    monkeypatch.setattr(resume, "AgentRepository", _Repo)
    monkeypatch.setattr(resume, "get_session_factory", lambda: _FakeFactory())

    outs = []
    async for evt in resume.resume_from_checkpoint("s1", "ckpt1"):
        outs.append(evt)

    assert outs
    assert outs[0]["event"] == "error"
    assert "already resolved" in outs[0]["message"]


@pytest.mark.asyncio
async def test_resume_returns_async_iterator_of_dicts(monkeypatch):
    """resume_from_checkpoint 是 async generator,产出 dict(agent_chat 包装 SSE)。"""
    from app.domain.agent.langgraph_nodes import resume

    class _RepoMissing:
        def __init__(self, s): pass
        async def get_message(self, mid): return None

    monkeypatch.setattr(resume, "AgentRepository", _RepoMissing)
    monkeypatch.setattr(resume, "get_session_factory", lambda: _FakeFactory())

    agen = resume.resume_from_checkpoint("s1", "x")
    first = await agen.__anext__()
    assert isinstance(first, dict)
    assert first["event"] == "error"