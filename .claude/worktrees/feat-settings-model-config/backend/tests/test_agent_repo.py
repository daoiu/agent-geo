"""Tests for AgentRepository (v0.4)."""
from __future__ import annotations

import json
from datetime import datetime, timezone

import pytest

from app.repositories.agent_repo import AgentRepository


def _to_naive(dt: datetime) -> datetime:
    """Normalize a datetime to naive UTC for comparison.

    SQLite returns naive datetimes even though the column is timezone-aware.
    """
    if dt.tzinfo is not None:
        dt = dt.astimezone(timezone.utc)
    return dt.replace(tzinfo=None)


@pytest.mark.asyncio
async def test_create_session_default_title(db_session) -> None:
    """不传 title 时使用默认标题'新对话'。"""
    repo = AgentRepository(db_session)
    s = await repo.create_session()
    assert s.id != ""
    assert s.title == "新对话"


@pytest.mark.asyncio
async def test_create_session_custom_title(db_session) -> None:
    """传入 title 时使用。"""
    repo = AgentRepository(db_session)
    s = await repo.create_session(title="诊断小米")
    assert s.title == "诊断小米"


@pytest.mark.asyncio
async def test_get_session_returns_none_when_missing(db_session) -> None:
    """不存在的 id 返回 None。"""
    repo = AgentRepository(db_session)
    assert await repo.get_session("does-not-exist") is None


@pytest.mark.asyncio
async def test_get_session_returns_existing(db_session) -> None:
    """存在的 id 返回对应 session。"""
    repo = AgentRepository(db_session)
    s = await repo.create_session(title="X")
    fetched = await repo.get_session(s.id)
    assert fetched is not None
    assert fetched.id == s.id
    assert fetched.title == "X"


@pytest.mark.asyncio
async def test_list_sessions_orders_by_updated_desc(db_session) -> None:
    """list_sessions 按 updated_at 倒序。"""
    repo = AgentRepository(db_session)
    s1 = await repo.create_session(title="A")
    s2 = await repo.create_session(title="B")
    sessions = await repo.list_sessions()
    assert len(sessions) >= 2
    # s2 后建，updated_at 更新，应排在前面
    assert sessions[0].id == s2.id
    assert s1.id in {s.id for s in sessions}


@pytest.mark.asyncio
async def test_delete_session_removes(db_session) -> None:
    """delete_session 后 get_session 返回 None。"""
    repo = AgentRepository(db_session)
    s = await repo.create_session(title="X")
    await repo.delete_session(s.id)
    assert await repo.get_session(s.id) is None


@pytest.mark.asyncio
async def test_update_session_title(db_session) -> None:
    """update_session_title 修改 title 并 bump updated_at。"""
    import asyncio

    repo = AgentRepository(db_session)
    s = await repo.create_session(title="X")
    original_updated = _to_naive(s.updated_at)
    await asyncio.sleep(0.01)  # 保证时间戳不同
    await repo.update_session_title(s.id, "新标题")
    fetched = await repo.get_session(s.id)
    assert fetched.title == "新标题"
    assert _to_naive(fetched.updated_at) > original_updated


@pytest.mark.asyncio
async def test_update_session_title_missing_returns_silently(db_session) -> None:
    """不存在的 id 不报错。"""
    repo = AgentRepository(db_session)
    await repo.update_session_title("does-not-exist", "Y")  # 不报错


@pytest.mark.asyncio
async def test_create_message_minimal(db_session) -> None:
    """create_message 最简形态。"""
    repo = AgentRepository(db_session)
    s = await repo.create_session(title="X")
    m = await repo.create_message(session_id=s.id, role="user", content="hi")
    assert m.id != ""
    assert m.role == "user"
    assert m.content == "hi"
    assert m.pending_confirmation == 0
    assert m.tool_calls is None


@pytest.mark.asyncio
async def test_create_message_with_tool_calls(db_session) -> None:
    """tool_calls list 被序列化为 JSON 字符串存储。"""
    repo = AgentRepository(db_session)
    s = await repo.create_session(title="X")
    tc = [{"id": "tc1", "function": {"name": "diagnose_brand", "arguments": "{}"}}]
    m = await repo.create_message(
        session_id=s.id, role="assistant", content=None, tool_calls=tc,
    )
    assert m.tool_calls is not None
    decoded = json.loads(m.tool_calls)
    assert decoded[0]["function"]["name"] == "diagnose_brand"


@pytest.mark.asyncio
async def test_create_message_pending_confirmation(db_session) -> None:
    """pending_confirmation=True 存为 1。"""
    repo = AgentRepository(db_session)
    s = await repo.create_session(title="X")
    m = await repo.create_message(
        session_id=s.id, role="assistant", content="...",
        pending_confirmation=True,
    )
    assert m.pending_confirmation == 1


@pytest.mark.asyncio
async def test_create_message_bumps_session_timestamp(db_session) -> None:
    """create_message 应同时 bump session 的 updated_at。"""
    import asyncio

    repo = AgentRepository(db_session)
    s = await repo.create_session(title="X")
    original_updated = _to_naive(s.updated_at)
    await asyncio.sleep(0.01)  # 确保时间戳不同
    await repo.create_message(session_id=s.id, role="user", content="hi")
    fetched = await repo.get_session(s.id)
    assert _to_naive(fetched.updated_at) > original_updated


@pytest.mark.asyncio
async def test_list_messages_orders_by_created_at(db_session) -> None:
    """list_messages 按 created_at 升序。"""
    repo = AgentRepository(db_session)
    s = await repo.create_session(title="X")
    m1 = await repo.create_message(session_id=s.id, role="user", content="1")
    m2 = await repo.create_message(session_id=s.id, role="assistant", content="2")
    messages = await repo.list_messages(s.id)
    assert len(messages) == 2
    assert messages[0].id == m1.id
    assert messages[1].id == m2.id


@pytest.mark.asyncio
async def test_get_message(db_session) -> None:
    """get_message 按 id 查。"""
    repo = AgentRepository(db_session)
    s = await repo.create_session(title="X")
    m = await repo.create_message(session_id=s.id, role="user", content="hi")
    fetched = await repo.get_message(m.id)
    assert fetched is not None
    assert fetched.id == m.id


@pytest.mark.asyncio
async def test_get_message_missing_returns_none(db_session) -> None:
    """不存在的 message_id 返回 None。"""
    repo = AgentRepository(db_session)
    assert await repo.get_message("missing") is None


@pytest.mark.asyncio
async def test_confirm_message_marks_resolved(db_session) -> None:
    """confirm_message 把 pending_confirmation 改回 0。"""
    repo = AgentRepository(db_session)
    s = await repo.create_session(title="X")
    m = await repo.create_message(
        session_id=s.id, role="assistant", content="...",
        pending_confirmation=True,
    )
    assert m.pending_confirmation == 1
    await repo.confirm_message(m.id, approved=True)
    fetched = await repo.get_message(m.id)
    assert fetched.pending_confirmation == 0


@pytest.mark.asyncio
async def test_confirm_message_rejected_also_resolves(db_session) -> None:
    """approved=False 同样 resolve（标记为已处理）。"""
    repo = AgentRepository(db_session)
    s = await repo.create_session(title="X")
    m = await repo.create_message(
        session_id=s.id, role="assistant", content="...",
        pending_confirmation=True,
    )
    await repo.confirm_message(m.id, approved=False)
    fetched = await repo.get_message(m.id)
    assert fetched.pending_confirmation == 0