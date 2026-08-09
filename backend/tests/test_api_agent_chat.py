"""Integration tests for agent chat SSE API (v0.4)."""
from __future__ import annotations

import asyncio
import json
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient


def test_post_message_returns_sse_stream(client: TestClient) -> None:
    """POST messages 返回 text/event-stream。"""
    create = client.post("/api/agent/sessions", json={"title": "T"})
    sid = create.json()["id"]

    with patch("app.api.agent_chat.run_agent_turn") as mock_run:
        # CR-2: run_agent_turn 产 SSE 字节流(非 dict),API 透传 bytes
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
            assert "text/event-stream" in resp.headers["content-type"]
            chunks = list(resp.iter_text())
            assert any("event: assistant_message" in c for c in chunks)
            assert any("event: turn_complete" in c for c in chunks)


def test_post_message_missing_session_returns_404(client: TestClient) -> None:
    """不存在的 session 返回 404。"""
    resp = client.post(
        "/api/agent/sessions/missing/messages",
        json={"content": "hi"},
    )
    assert resp.status_code == 404


def test_post_message_empty_content_fails(client: TestClient) -> None:
    """空 content 被 Pydantic 拒绝。"""
    create = client.post("/api/agent/sessions", json={"title": "T"})
    sid = create.json()["id"]
    resp = client.post(
        f"/api/agent/sessions/{sid}/messages", json={"content": ""}
    )
    assert resp.status_code == 422


def test_confirm_action_approves(client: TestClient) -> None:
    """approved=True 调用 resume_from_checkpoint 并 stream SSE。"""
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

    with patch("app.api.agent_chat.resume_from_checkpoint") as mock_resume:
        async def fake_events(*args, **kwargs):
            yield (f"event: tool_call_result\ndata: {json.dumps({'tool_call_id': 'tc1', 'result': {'x': 1}}, ensure_ascii=False)}\n\n").encode("utf-8")
            yield (f"event: assistant_message\ndata: {json.dumps({'content': '已生成'}, ensure_ascii=False)}\n\n").encode("utf-8")
            yield (f"event: turn_complete\ndata: {json.dumps({}, ensure_ascii=False)}\n\n").encode("utf-8")
        mock_resume.side_effect = fake_events

        with client.stream(
            "POST",
            f"/api/agent/sessions/{sid}/messages/{msg_id}/confirm",
            json={"approved": True},
        ) as resp:
            assert resp.status_code == 200
            assert "text/event-stream" in resp.headers["content-type"]
            chunks = list(resp.iter_text())
            assert any("event: tool_call_result" in c for c in chunks)
            assert any("event: turn_complete" in c for c in chunks)
            mock_resume.assert_called_once()


def test_confirm_action_rejects(client: TestClient) -> None:
    """approved=False 写'取消'消息并返回 cancelled。"""
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
    assert body["message_id"] == msg_id


def test_confirm_action_missing_message_returns_404(client: TestClient) -> None:
    """不存在的 message 返回 404。"""
    create = client.post("/api/agent/sessions", json={"title": "T"})
    sid = create.json()["id"]
    resp = client.post(
        f"/api/agent/sessions/{sid}/messages/missing/confirm",
        json={"approved": True},
    )
    assert resp.status_code == 404


def test_confirm_action_already_resolved_returns_409(client: TestClient) -> None:
    """已经 resolved 的 message 返回 409。"""
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
            # 标记为 resolved
            await repo.confirm_message(msg.id, approved=True)
            return sess.id, msg.id

    sid, msg_id = asyncio.run(_setup())

    resp = client.post(
        f"/api/agent/sessions/{sid}/messages/{msg_id}/confirm",
        json={"approved": True},
    )
    assert resp.status_code == 409


def test_confirm_action_wrong_session_returns_404(client: TestClient) -> None:
    """message 不属于指定 session 时返回 404。"""
    from app.core.db import get_session_factory
    from app.repositories.agent_repo import AgentRepository

    async def _setup() -> tuple[str, str, str]:
        async with get_session_factory()() as s:
            repo = AgentRepository(s)
            sess_a = await repo.create_session(title="A")
            sess_b = await repo.create_session(title="B")
            msg = await repo.create_message(
                session_id=sess_a.id, role="assistant", content="...",
                pending_confirmation=True,
            )
            return sess_a.id, sess_b.id, msg.id

    sid_a, sid_b, msg_id = asyncio.run(_setup())

    # 用 sid_b 访问 sess_a 的 msg → 404
    resp = client.post(
        f"/api/agent/sessions/{sid_b}/messages/{msg_id}/confirm",
        json={"approved": True},
    )
    assert resp.status_code == 404


# ===========================================================================
# v0.6+ P1#14（Task 15）：HumanConfirmation 专项 edge case
# ===========================================================================


def test_confirm_reject_writes_cancel_messages_to_db(client: TestClient) -> None:
    """reject 应在 DB 追加 '取消' user + '好的,已取消。' assistant 两条消息。

    验证 reject 副作用完整,不只是返回 JSON。
    """
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

    # 验证 DB:原 pending msg 被 resolved,且追加了 2 条消息
    async def _verify() -> None:
        async with get_session_factory()() as s:
            repo = AgentRepository(s)
            original = await repo.get_message(msg_id)
            assert original.pending_confirmation == 0, "pending msg 应被 resolved"

            msgs = await repo.list_messages(sid)
            contents = [m.content for m in msgs]
            assert "取消" in contents, f"应有 '取消' user 消息,实际 {contents}"
            assert any("已取消" in c for c in contents), (
                f"应有 '好的,已取消。' assistant 消息,实际 {contents}"
            )

    asyncio.run(_verify())


def test_confirm_reject_then_approve_returns_409(client: TestClient) -> None:
    """同一 pending msg 先 reject,再 approve 应 409(已 resolved)。

    验证 state machine:reject 后消息不可再被 approve。
    """
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

    # 第一次 reject 应成功
    resp1 = client.post(
        f"/api/agent/sessions/{sid}/messages/{msg_id}/confirm",
        json={"approved": False},
    )
    assert resp1.status_code == 200

    # 第二次 approve 应 409
    resp2 = client.post(
        f"/api/agent/sessions/{sid}/messages/{msg_id}/confirm",
        json={"approved": True},
    )
    assert resp2.status_code == 409


def test_confirm_wrong_session_leaves_msg_pending(client: TestClient) -> None:
    """跨 session 访问 404 应不改 pending 状态(不应误 resolve)。

    防止 404 路径误改 DB。
    """
    from app.core.db import get_session_factory
    from app.repositories.agent_repo import AgentRepository

    async def _setup() -> tuple[str, str, str]:
        async with get_session_factory()() as s:
            repo = AgentRepository(s)
            sess_a = await repo.create_session(title="A")
            sess_b = await repo.create_session(title="B")
            msg = await repo.create_message(
                session_id=sess_a.id, role="assistant", content="...",
                pending_confirmation=True,
            )
            return sess_a.id, sess_b.id, msg.id

    sid_a, sid_b, msg_id = asyncio.run(_setup())

    # 用 sid_b 访问 sess_a 的 msg → 404
    resp = client.post(
        f"/api/agent/sessions/{sid_b}/messages/{msg_id}/confirm",
        json={"approved": False},
    )
    assert resp.status_code == 404

    # 验证 msg 仍为 pending
    async def _verify() -> None:
        async with get_session_factory()() as s:
            repo = AgentRepository(s)
            m = await repo.get_message(msg_id)
            assert m.pending_confirmation == 1, (
                f"404 不应改 pending 状态,实际 {m.pending_confirmation}"
            )

    asyncio.run(_verify())