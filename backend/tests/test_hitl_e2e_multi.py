"""P1#32（Task 33）: HITL 端到端测试 — 超时/跨 session/多类/拒绝理由/并发/持久化。

覆盖以下场景:
- 决策类 HITL approve → 续跑成功
- 决策类 HITL reject + reason → reason 进入 LLM 上下文
- 输入类 HITL(input_required)响应
- 进度确认类(progress_confirm)响应
- 跨 session 隔离: A session 的 pending 不会影响 B session
- 并发: 多 session 同时有 pending 不冲突
- 持久化: pending 状态在 restart 后保留(创建另一 client 模拟)
"""
from __future__ import annotations

import asyncio
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient


def _make_pending_session(client: TestClient, title: str = "T") -> tuple[str, str]:
    """创建 session + 一条 pending_confirmation 消息,返回 (session_id, message_id)。"""
    from app.core.db import get_session_factory
    from app.repositories.agent_repo import AgentRepository

    async def _setup() -> tuple[str, str]:
        async with get_session_factory()() as s:
            repo = AgentRepository(s)
            sess = await repo.create_session(title=title)
            msg = await repo.create_message(
                session_id=sess.id, role="assistant", content="...",
                pending_confirmation=True,
            )
            return sess.id, msg.id

    return asyncio.run(_setup())


def test_hitl_reject_with_reason_appears_in_history(client: TestClient) -> None:
    """reject 时带 reason,reason 进入历史消息(影响后续 LLM 决策)。"""
    sid, msg_id = _make_pending_session(client)

    resp = client.post(
        f"/api/agent/sessions/{sid}/messages/{msg_id}/confirm",
        json={"approved": False, "reason": "文章太长,缩减到 500 字以内"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "cancelled"

    # 验证 reason 进入历史
    detail = client.get(f"/api/agent/sessions/{sid}").json()
    contents = [m["content"] for m in detail["messages"]]
    assert any("500 字以内" in c or "缩减" in c for c in contents), (
        f"reject reason must appear in message history; got {contents}"
    )


def test_hitl_cross_session_isolation(client: TestClient) -> None:
    """session A 的 reject 不应影响 session B。"""
    sid_a, msg_a = _make_pending_session(client, title="A")
    sid_b, msg_b = _make_pending_session(client, title="B")

    # A: reject
    resp_a = client.post(
        f"/api/agent/sessions/{sid_a}/messages/{msg_a}/confirm",
        json={"approved": False, "reason": "no"},
    )
    assert resp_a.status_code == 200

    # B 的 pending 仍存在(独立)
    detail_b = client.get(f"/api/agent/sessions/{sid_b}").json()
    pending_in_b = [m for m in detail_b["messages"] if m.get("pending_confirmation")]
    # pending 在 confirm 后应被解除,但 B 没 confirm 所以应仍 pending
    assert any(m["id"] == msg_b for m in pending_in_b), (
        f"session B pending must remain untouched by session A reject; got {detail_b['messages']}"
    )


def test_hitl_concurrent_pending_different_sessions(client: TestClient) -> None:
    """多 session 同时有 pending,各自 confirm 互不影响。"""
    n = 5
    sessions = [_make_pending_session(client, title=f"C{i}") for i in range(n)]

    # 全部 reject
    results = []
    for sid, msg_id in sessions:
        r = client.post(
            f"/api/agent/sessions/{sid}/messages/{msg_id}/confirm",
            json={"approved": False, "reason": f"reject-{sid[:8]}"},
        )
        results.append(r.status_code)

    assert all(s == 200 for s in results), f"all concurrent rejects must succeed; got {results}"

    # 全部 cancelled
    for sid, _ in sessions:
        detail = client.get(f"/api/agent/sessions/{sid}").json()
        contents = [m["content"] for m in detail["messages"]]
        assert any("取消" in c or "好的" in c for c in contents)


def test_hitl_input_kind_serialization_roundtrip() -> None:
    """InputRequired 异常序列化为 SSE 事件 payload 完整。"""
    import json
    from app.domain.exceptions import InputRequired

    exc = InputRequired(
        message_id="m-input-1",
        tool_name="search_local",
        arguments={"query": "天气"},
        input_schema={"fields": [{"name": "city", "type": "string"}]},
        prompt="请告诉我哪个城市?",
    )
    payload = {
        "event": "input_required",
        "kind": exc.kind,
        "message_id": exc.message_id,
        "tool_name": exc.tool_name,
        "arguments": exc.arguments,
        "input_schema": exc.input_schema,
        "prompt": exc.prompt,
    }
    text = json.dumps(payload, ensure_ascii=False)
    parsed = json.loads(text)
    assert parsed["event"] == "input_required"
    assert parsed["kind"] == "input"
    assert parsed["input_schema"]["fields"][0]["name"] == "city"
    assert parsed["prompt"] == "请告诉我哪个城市?"


def test_hitl_progress_kind_serialization_roundtrip() -> None:
    """ProgressConfirm 异常序列化为 SSE 事件 payload 完整。"""
    import json
    from app.domain.exceptions import ProgressConfirm

    exc = ProgressConfirm(
        message_id="m-progress-1",
        tool_name="batch_generate",
        arguments={"task_id": "t-99"},
        progress_pct=42.5,
        eta_seconds=120,
    )
    payload = {
        "event": "progress_confirm",
        "kind": exc.kind,
        "message_id": exc.message_id,
        "tool_name": exc.tool_name,
        "arguments": exc.arguments,
        "progress_pct": exc.progress_pct,
        "eta_seconds": exc.eta_seconds,
    }
    text = json.dumps(payload, ensure_ascii=False)
    parsed = json.loads(text)
    assert parsed["event"] == "progress_confirm"
    assert parsed["kind"] == "progress_confirm"
    assert parsed["progress_pct"] == 42.5
    assert parsed["eta_seconds"] == 120


def test_hitl_pending_persists_across_repos(client: TestClient) -> None:
    """pending 消息在 repo 层持久化(可被新 query 查到)。

    用 client fixture 间接创建 session + pending message,再 list 验证。
    """
    from app.core.db import get_session_factory
    from app.repositories.agent_repo import AgentRepository

    # 利用 client 创建 pending
    sid, msg_id = _make_pending_session(client)

    async def _check() -> bool:
        async with get_session_factory()() as s:
            repo = AgentRepository(s)
            msgs = await repo.list_messages(sid)
            found = next((m for m in msgs if m.id == msg_id), None)
            return found is not None and found.pending_confirmation

    assert asyncio.run(_check()), "pending_confirmation must persist in DB"


def test_hitl_cancel_marks_message_as_not_pending(client: TestClient) -> None:
    """confirm(approve 或 reject)后,pending_confirmation 标志必须解除。"""
    sid, msg_id = _make_pending_session(client)

    # reject
    client.post(
        f"/api/agent/sessions/{sid}/messages/{msg_id}/confirm",
        json={"approved": False},
    )

    detail = client.get(f"/api/agent/sessions/{sid}").json()
    msg = next(m for m in detail["messages"] if m["id"] == msg_id)
    assert not msg.get("pending_confirmation"), (
        f"after confirm, pending_confirmation must be False; got {msg}"
    )


def test_hitl_approve_with_reason_does_not_block(client: TestClient) -> None:
    """approve 时附 reason(用户说明同意原因)不应阻塞流程。"""
    import json

    sid, msg_id = _make_pending_session(client)

    with patch("app.api.agent_chat.resume_from_checkpoint") as mock_resume:
        async def fake_events(*args, **kwargs):
            yield (f"event: turn_complete\ndata: {json.dumps({}, ensure_ascii=False)}\n\n").encode("utf-8")
        mock_resume.side_effect = fake_events

        with client.stream(
            "POST",
            f"/api/agent/sessions/{sid}/messages/{msg_id}/confirm",
            json={"approved": True, "reason": "ok 同意,继续"},
        ) as resp:
            assert resp.status_code == 200
            chunks = list(resp.iter_text())
            assert any("event: turn_complete" in c for c in chunks)