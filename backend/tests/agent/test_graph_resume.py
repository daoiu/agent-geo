"""T7 验证:HITL generate_article 确认续跑迁到图 resume。

CR-2:resume_from_checkpoint 签名 AsyncIterator[bytes](spec L445 字节契约),
SSEBridge._dispatch 直接产 SSE 字节,agent_chat 透传给 StreamingResponse。
"""
from __future__ import annotations

import json

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


def _decode(byts: bytes) -> dict:
    """SSE 字节流(单 chunk 含一个 JSON dict + \\n)→ dict。"""
    return json.loads(byts.decode("utf-8").strip())


@pytest.mark.asyncio
async def test_resume_missing_checkpoint_yields_error_bytes(monkeypatch):
    """checkpoint message 不存在 → resume_from_checkpoint yield SSE error 字节。"""
    from app.domain.agent.langgraph_nodes import resume

    class _RepoMissing:
        def __init__(self, s): pass
        async def get_message(self, mid): return None

    monkeypatch.setattr(resume, "AgentRepository", _RepoMissing)
    monkeypatch.setattr(resume, "get_session_factory", lambda: _FakeFactory())

    outs = []
    async for sse_bytes in resume.resume_from_checkpoint("s1", "missing-id"):
        outs.append(_decode(sse_bytes))

    assert outs, "expected at least one SSE chunk"
    assert outs[0]["event"] == "error"
    assert "missing-id" in outs[0]["message"] or "not found" in outs[0]["message"]


@pytest.mark.asyncio
async def test_resume_already_resolved_yields_error_bytes(monkeypatch):
    """checkpoint 已 resolved(pending_confirmation=False)→ yield SSE error 字节。"""
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
    async for sse_bytes in resume.resume_from_checkpoint("s1", "ckpt1"):
        outs.append(_decode(sse_bytes))

    assert outs
    assert outs[0]["event"] == "error"
    assert "already resolved" in outs[0]["message"]


@pytest.mark.asyncio
async def test_resume_returns_async_iterator_of_bytes(monkeypatch):
    """resume_from_checkpoint 是 async generator,产出 bytes(agent_chat 透传)。"""
    from app.domain.agent.langgraph_nodes import resume

    class _RepoMissing:
        def __init__(self, s): pass
        async def get_message(self, mid): return None

    monkeypatch.setattr(resume, "AgentRepository", _RepoMissing)
    monkeypatch.setattr(resume, "get_session_factory", lambda: _FakeFactory())

    agen = resume.resume_from_checkpoint("s1", "x")
    first = await agen.__anext__()
    assert isinstance(first, bytes)
    assert _decode(first)["event"] == "error"