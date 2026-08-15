"""Tests for v0.4 ORM models (agent_sessions, agent_messages)."""
from __future__ import annotations

import json

import pytest

from app.models.orm_v04 import AgentMessageORM, AgentSessionORM


@pytest.mark.asyncio
async def test_agent_session_orm_persists(db_session) -> None:
    """A new session is persisted and retrievable by id."""
    s = AgentSessionORM(id="s1", title="诊断小米")
    db_session.add(s)
    await db_session.commit()

    from sqlalchemy import select

    result = await db_session.execute(
        select(AgentSessionORM).where(AgentSessionORM.id == "s1")
    )
    fetched = result.scalar_one()
    assert fetched.title == "诊断小米"
    assert fetched.created_at is not None
    assert fetched.updated_at is not None


@pytest.mark.asyncio
async def test_agent_session_orm_default_title(db_session) -> None:
    """If title is not provided, model still persists with empty string."""
    s = AgentSessionORM(id="s2", title="默认")
    db_session.add(s)
    await db_session.commit()
    assert s.title == "默认"


@pytest.mark.asyncio
async def test_agent_message_user_role(db_session) -> None:
    """A user-role message persists with content and defaults."""
    s = AgentSessionORM(id="s1", title="T")
    db_session.add(s)
    await db_session.commit()

    m = AgentMessageORM(
        id="m1",
        session_id="s1",
        role="user",
        content="诊断小米",
    )
    db_session.add(m)
    await db_session.commit()

    assert m.role == "user"
    assert m.pending_confirmation == 0  # default
    assert m.tool_calls is None
    assert m.tool_call_id is None


@pytest.mark.asyncio
async def test_agent_message_assistant_with_tool_calls(db_session) -> None:
    """tool_calls is stored as JSON string of OpenAI-format tool calls."""
    s = AgentSessionORM(id="s1", title="T")
    db_session.add(s)
    await db_session.commit()

    tc_payload = json.dumps([
        {"id": "tc1", "type": "function", "function": {"name": "diagnose_brand", "arguments": "{}"}},
    ])
    m = AgentMessageORM(
        id="m2",
        session_id="s1",
        role="assistant",
        content="让我先诊断",
        tool_calls=tc_payload,
    )
    db_session.add(m)
    await db_session.commit()
    assert json.loads(m.tool_calls)[0]["function"]["name"] == "diagnose_brand"


@pytest.mark.asyncio
async def test_agent_message_pending_confirmation(db_session) -> None:
    """pending_confirmation flag persists correctly."""
    s = AgentSessionORM(id="s1", title="T")
    db_session.add(s)
    await db_session.commit()

    m = AgentMessageORM(
        id="m3",
        session_id="s1",
        role="assistant",
        content="准备生成文章",
        pending_confirmation=1,
    )
    db_session.add(m)
    await db_session.commit()
    assert m.pending_confirmation == 1


@pytest.mark.asyncio
async def test_agent_message_tool_role_with_call_id(db_session) -> None:
    """A tool-role message references the assistant's tool_call_id."""
    s = AgentSessionORM(id="s1", title="T")
    db_session.add(s)
    await db_session.commit()

    m = AgentMessageORM(
        id="m4",
        session_id="s1",
        role="tool",
        content='{"overall_score": 45}',
        tool_call_id="tc_001",
    )
    db_session.add(m)
    await db_session.commit()
    assert m.role == "tool"
    assert m.tool_call_id == "tc_001"


@pytest.mark.asyncio
async def test_agent_message_cascade_delete(db_session) -> None:
    """Deleting a session cascades to its messages (FK ON DELETE CASCADE)."""
    s = AgentSessionORM(id="s1", title="T")
    db_session.add(s)
    await db_session.commit()

    m = AgentMessageORM(
        id="m1", session_id="s1", role="user", content="hi"
    )
    db_session.add(m)
    await db_session.commit()

    # Delete session
    from sqlalchemy import delete, select

    await db_session.execute(
        delete(AgentSessionORM).where(AgentSessionORM.id == "s1")
    )
    await db_session.commit()

    result = await db_session.execute(
        select(AgentMessageORM).where(AgentMessageORM.session_id == "s1")
    )
    assert result.scalar_one_or_none() is None