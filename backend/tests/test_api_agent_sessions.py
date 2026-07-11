"""Integration tests for agent session CRUD API (v0.4)."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


def test_create_session_with_title(client: TestClient) -> None:
    """POST /api/agent/sessions 带 title 创建。"""
    resp = client.post("/api/agent/sessions", json={"title": "诊断小米"})
    assert resp.status_code == 201
    body = resp.json()
    assert body["title"] == "诊断小米"
    assert "id" in body
    assert "created_at" in body
    assert "updated_at" in body


def test_create_session_default_title(client: TestClient) -> None:
    """POST /api/agent/sessions 不带 title → 默认'新对话'。"""
    resp = client.post("/api/agent/sessions", json={})
    assert resp.status_code == 201
    assert resp.json()["title"] == "新对话"


def test_list_sessions(client: TestClient) -> None:
    """GET /api/agent/sessions 列出所有 session。"""
    client.post("/api/agent/sessions", json={"title": "A"})
    client.post("/api/agent/sessions", json={"title": "B"})
    resp = client.get("/api/agent/sessions")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 2
    titles = {s["title"] for s in body}
    assert titles == {"A", "B"}


def test_get_session_with_messages(client: TestClient) -> None:
    """GET /api/agent/sessions/{id} 返回 session + messages。"""
    import asyncio

    from app.core.db import get_session_factory
    from app.repositories.agent_repo import AgentRepository

    async def _setup() -> str:
        async with get_session_factory()() as s:
            repo = AgentRepository(s)
            sess = await repo.create_session(title="T")
            await repo.create_message(session_id=sess.id, role="user", content="hi")
            await repo.create_message(session_id=sess.id, role="assistant", content="hello")
            return sess.id

    sid = asyncio.run(_setup())

    resp = client.get(f"/api/agent/sessions/{sid}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["id"] == sid
    assert body["title"] == "T"
    assert len(body["messages"]) == 2
    assert body["messages"][0]["role"] == "user"
    assert body["messages"][0]["content"] == "hi"
    assert body["messages"][1]["role"] == "assistant"


def test_get_session_missing_returns_404(client: TestClient) -> None:
    """不存在的 session 返回 404。"""
    resp = client.get("/api/agent/sessions/does-not-exist")
    assert resp.status_code == 404


def test_get_session_with_tool_calls_message(client: TestClient) -> None:
    """回归：assistant 消息带 tool_calls（DB 存 JSON 字符串）时 GET 详情不 500。

    tool_calls 列在 DB 是 Text(JSON 字符串)，响应 schema 需把它反序列化为 list，
    否则 AgentMessage.model_validate 抛 ValidationError -> 500。
    """
    import asyncio

    from app.core.db import get_session_factory
    from app.repositories.agent_repo import AgentRepository

    tool_calls = [
        {
            "id": "call_1",
            "function": {"name": "list_knowledge_bases", "arguments": "{}"},
        }
    ]

    async def _setup() -> str:
        async with get_session_factory()() as s:
            repo = AgentRepository(s)
            sess = await repo.create_session(title="T")
            await repo.create_message(
                session_id=sess.id, role="assistant",
                content="我来列一下知识库", tool_calls=tool_calls,
            )
            return sess.id

    sid = asyncio.run(_setup())

    resp = client.get(f"/api/agent/sessions/{sid}")
    assert resp.status_code == 200
    msg = resp.json()["messages"][0]
    assert isinstance(msg["tool_calls"], list)
    assert msg["tool_calls"][0]["function"]["name"] == "list_knowledge_bases"
    assert msg["tool_calls"][0]["function"]["arguments"] == "{}"


def test_delete_session(client: TestClient) -> None:
    """DELETE 后 GET 返回 404。"""
    create = client.post("/api/agent/sessions", json={"title": "X"})
    sid = create.json()["id"]
    resp = client.delete(f"/api/agent/sessions/{sid}")
    assert resp.status_code == 204
    get_resp = client.get(f"/api/agent/sessions/{sid}")
    assert get_resp.status_code == 404


def test_delete_session_missing_returns_404(client: TestClient) -> None:
    """删除不存在的 session 返回 404。"""
    resp = client.delete("/api/agent/sessions/does-not-exist")
    assert resp.status_code == 404


def test_update_session_title(client: TestClient) -> None:
    """PATCH 修改 title。"""
    create = client.post("/api/agent/sessions", json={"title": "X"})
    sid = create.json()["id"]
    resp = client.patch(
        f"/api/agent/sessions/{sid}", json={"title": "新标题"}
    )
    assert resp.status_code == 200
    assert resp.json()["title"] == "新标题"


def test_update_session_title_empty_fails(client: TestClient) -> None:
    """title 为空字符串 → 422 校验失败。"""
    create = client.post("/api/agent/sessions", json={"title": "X"})
    sid = create.json()["id"]
    resp = client.patch(f"/api/agent/sessions/{sid}", json={"title": ""})
    assert resp.status_code == 422