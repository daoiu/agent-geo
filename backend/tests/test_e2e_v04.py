"""E2E tests for v0.4 agent flow (no mocking)."""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient


def test_e2e_create_session_and_list(client: TestClient) -> None:
    """创建 session 后能列出来。"""
    resp = client.post("/api/agent/sessions", json={"title": "E2E Test"})
    assert resp.status_code == 201
    sid = resp.json()["id"]

    list_resp = client.get("/api/agent/sessions")
    assert list_resp.status_code == 200
    assert any(s["id"] == sid for s in list_resp.json())


def test_e2e_session_detail_includes_messages(client: TestClient) -> None:
    """Session 详情返回完整消息历史。"""
    import asyncio

    from app.core.db import get_session_factory
    from app.repositories.agent_repo import AgentRepository

    async def _setup() -> str:
        async with get_session_factory()() as s:
            repo = AgentRepository(s)
            sess = await repo.create_session(title="T")
            await repo.create_message(session_id=sess.id, role="user", content="hi")
            return sess.id

    sid = asyncio.run(_setup())

    resp = client.get(f"/api/agent/sessions/{sid}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["id"] == sid
    assert len(body["messages"]) == 1
    assert body["messages"][0]["content"] == "hi"


def test_e2e_post_message_streams_sse(client: TestClient) -> None:
    """POST /messages 返回 SSE 流。"""
    import json

    create = client.post("/api/agent/sessions", json={"title": "T"})
    sid = create.json()["id"]

    with patch("app.api.agent_chat.run_agent_turn") as mock_run:
        # CR-2: run_agent_turn 产 SSE 字节流(非 dict)
        async def fake_events(*args, **kwargs):
            yield (f"event: assistant_message\ndata: {json.dumps({'content': '好的'}, ensure_ascii=False)}\n\n").encode("utf-8")
            yield (f"event: turn_complete\ndata: {json.dumps({}, ensure_ascii=False)}\n\n").encode("utf-8")
        mock_run.side_effect = fake_events

        with client.stream(
            "POST",
            f"/api/agent/sessions/{sid}/messages",
            json={"content": "诊断小米"},
        ) as resp:
            assert resp.status_code == 200
            chunks = list(resp.iter_text())
            assert any("event: turn_complete" in c for c in chunks)


def test_e2e_human_confirmation_pause_and_resume(client: TestClient) -> None:
    """完整流程：generate_article → 暂停 → confirm → 续跑。"""
    import asyncio
    import json

    from app.core.db import get_session_factory
    from app.repositories.agent_repo import AgentRepository

    async def _setup() -> tuple[str, str]:
        async with get_session_factory()() as s:
            repo = AgentRepository(s)
            sess = await repo.create_session(title="T")
            msg = await repo.create_message(
                session_id=sess.id, role="assistant", content="...",
                pending_confirmation=True,
            )
            return sess.id, msg.id

    sid, msg_id = asyncio.run(_setup())

    # approved=True → 调 resume_from_checkpoint 并 stream SSE 字节流
    with patch("app.api.agent_chat.resume_from_checkpoint") as mock_resume:
        async def fake_events(*args, **kwargs):
            yield (f"event: tool_call_result\ndata: {json.dumps({'tool_call_id': 'tc1', 'result': {'status': 'generated'}}, ensure_ascii=False)}\n\n").encode("utf-8")
            yield (f"event: assistant_message\ndata: {json.dumps({'content': '已生成'}, ensure_ascii=False)}\n\n").encode("utf-8")
            yield (f"event: turn_complete\ndata: {json.dumps({}, ensure_ascii=False)}\n\n").encode("utf-8")
        mock_resume.side_effect = fake_events

        with client.stream(
            "POST",
            f"/api/agent/sessions/{sid}/messages/{msg_id}/confirm",
            json={"approved": True},
        ) as resp:
            assert resp.status_code == 200
            chunks = list(resp.iter_text())
            assert any("event: tool_call_result" in c for c in chunks)
            assert any("event: turn_complete" in c for c in chunks)
            mock_resume.assert_called_once_with(sid, msg_id, device_id=None)


def test_e2e_cancel_returns_json(client: TestClient) -> None:
    """approved=False 走 JSON 路径，写'取消'消息。"""
    import asyncio

    from app.core.db import get_session_factory
    from app.repositories.agent_repo import AgentRepository

    async def _setup() -> tuple[str, str]:
        async with get_session_factory()() as s:
            repo = AgentRepository(s)
            sess = await repo.create_session(title="T")
            msg = await repo.create_message(
                session_id=sess.id, role="assistant", content="...",
                pending_confirmation=True,
            )
            return sess.id, msg.id

    sid, msg_id = asyncio.run(_setup())

    resp = client.post(
        f"/api/agent/sessions/{sid}/messages/{msg_id}/confirm",
        json={"approved": False},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "cancelled"

    # 验证写了"取消"消息
    detail = client.get(f"/api/agent/sessions/{sid}").json()
    contents = [m["content"] for m in detail["messages"]]
    assert "取消" in contents
    assert "好的，已取消。" in contents