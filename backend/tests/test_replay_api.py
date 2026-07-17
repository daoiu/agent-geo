"""P2#32(Task 41): 显式 replay API 测试。

目标:
- POST /api/agent/sessions/{sid}/replay/{message_id} 端点
- 从任意 message_id (不只是 pending) 重放该 turn
- 返回 SSE 字节流 + 标注"replay_start"事件
- 权限: 验证 message 属于该 session

CR-3:patch 路径从 react_loop.run_agent_turn_from_checkpoint 改为
langgraph_nodes.resume.resume_from_checkpoint(T10 删 react_loop 后)。
"""
from __future__ import annotations

import asyncio
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient


def _create_session_and_message(client: TestClient, role: str = "user") -> tuple[str, str]:
    """创建 session + 一条消息,返回 (session_id, message_id)。"""
    from app.core.db import get_session_factory
    from app.repositories.agent_repo import AgentRepository

    async def _setup() -> tuple[str, str]:
        async with get_session_factory()() as s:
            repo = AgentRepository(s)
            sess = await repo.create_session(title="replay-test")
            msg = await repo.create_message(
                session_id=sess.id, role=role, content="小米诊断",
            )
            return sess.id, msg.id

    return asyncio.run(_setup())


def _sse_bytes(event: str, **fields) -> bytes:
    """构造 react_loop 等价的 SSE 字节:`event: ...\\ndata: {json}\\n\\n`"""
    import json
    data = {"event": event, **fields}
    return (
        f"event: {event}\n"
        f"data: {json.dumps(data, ensure_ascii=False)}\n\n"
    ).encode("utf-8")


def test_replay_endpoint_exists(client: TestClient) -> None:
    """replay 端点必须存在(返回 200/422/4xx,不返回 404 method)。"""
    sid, msg_id = _create_session_and_message(client)

    with patch("app.domain.agent.langgraph_nodes.resume.resume_from_checkpoint") as mock_r:
        async def fake_replay(*args, **kwargs):
            yield _sse_bytes("turn_complete")
        mock_r.side_effect = fake_replay

        with client.stream(
            "POST",
            f"/api/agent/sessions/{sid}/replay/{msg_id}",
        ) as resp:
            assert resp.status_code != 404, "replay endpoint must exist"
            assert resp.status_code != 405


def test_replay_emits_replay_marker_event(client: TestClient) -> None:
    """replay 流必须先 yield 一个 'replay_start' 标记事件(区分正常流)。"""
    sid, msg_id = _create_session_and_message(client)

    with patch("app.domain.agent.langgraph_nodes.resume.resume_from_checkpoint") as mock_r:
        async def fake_replay(*args, **kwargs):
            yield _sse_bytes("turn_complete")
        mock_r.side_effect = fake_replay

        with client.stream(
            "POST",
            f"/api/agent/sessions/{sid}/replay/{msg_id}",
        ) as resp:
            assert resp.status_code == 200
            chunks = list(resp.iter_text())
            assert any("event: replay_start" in c for c in chunks), (
                f"replay must emit replay_start event; chunks={chunks[:5]}"
            )


def test_replay_404_when_message_not_found(client: TestClient) -> None:
    """message_id 不存在应返回 404。"""
    sid, _ = _create_session_and_message(client)

    with client.stream(
        "POST",
        f"/api/agent/sessions/{sid}/replay/nonexistent-id",
    ) as resp:
        assert resp.status_code == 404


def test_replay_404_when_session_mismatch(client: TestClient) -> None:
    """message_id 属于另一 session 应返回 404。"""
    sid_a, _ = _create_session_and_message(client)
    _, msg_b = _create_session_and_message(client)  # 另一 session

    with client.stream(
        "POST",
        f"/api/agent/sessions/{sid_a}/replay/{msg_b}",
    ) as resp:
        assert resp.status_code == 404


def test_replay_emits_complete_event(client: TestClient) -> None:
    """replay 流最终必须 yield turn_complete。"""
    sid, msg_id = _create_session_and_message(client)

    with patch("app.domain.agent.langgraph_nodes.resume.resume_from_checkpoint") as mock_r:
        async def fake_replay(*args, **kwargs):
            yield _sse_bytes("tool_call_result", tool_call_id="tc1", result={"x": 1})
            yield _sse_bytes("assistant_message", content="重放结果")
            yield _sse_bytes("turn_complete")
        mock_r.side_effect = fake_replay

        with client.stream(
            "POST",
            f"/api/agent/sessions/{sid}/replay/{msg_id}",
        ) as resp:
            chunks = list(resp.iter_text())
            assert any("event: turn_complete" in c for c in chunks)


def test_replay_works_for_user_messages(client: TestClient) -> None:
    """replay 可针对 user 消息(不只 pending 消息)。"""
    sid, msg_id = _create_session_and_message(client, role="user")

    with patch("app.domain.agent.langgraph_nodes.resume.resume_from_checkpoint") as mock_r:
        async def fake_replay(*args, **kwargs):
            yield _sse_bytes("turn_complete")
        mock_r.side_effect = fake_replay

        with client.stream(
            "POST",
            f"/api/agent/sessions/{sid}/replay/{msg_id}",
        ) as resp:
            assert resp.status_code == 200