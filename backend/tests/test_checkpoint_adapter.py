"""Tests for CheckpointAdapter — LangGraph checkpoint ↔ pending_confirmation round-trip."""
from __future__ import annotations

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine


@pytest_asyncio.fixture
async def sqlite_session_factory():
    """Provide an in-memory SQLite session factory with agent_sessions table.

    Sets up the table schema needed by CheckpointAdapter (pending_confirmation
    JSON column + langgraph_thread_id UUID column) before each test.
    """
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    # Create table with the columns CheckpointAdapter expects.
    # NOTE: langgraph_thread_id column does NOT exist in the production schema yet
    # (Task 6 adds it). Here in tests we create it so the adapter skeleton works.
    async with engine.begin() as conn:
        await conn.execute(text("""
            CREATE TABLE agent_sessions (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL DEFAULT '',
                pending_confirmation TEXT,
                langgraph_thread_id TEXT
            )
        """))
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    yield session_factory
    await engine.dispose()


@pytest.mark.asyncio
async def test_round_trip_preserves_pending_confirmation(sqlite_session_factory):
    """persist → load_or_init → round_trip preserves pending_confirmation JSON."""
    from app.domain.agent.langgraph_nodes.checkpoint_adapter import CheckpointAdapter

    adapter = CheckpointAdapter(session_factory=sqlite_session_factory)

    # 1. Simulate HITL pause by persisting a snapshot
    await adapter.persist(
        session_id="s1",
        snapshot={
            "messages": [],
            "pending": {"tool_call_id": "tc1", "args": {"q": "x"}, "resume_token": "rt-1"},
        },
    )

    # 2. Round-trip load — data must match what was persisted
    snapshot, thread_id = await adapter.load_or_init("s1")
    assert snapshot["pending"]["tool_call_id"] == "tc1"
    assert snapshot["pending"]["resume_token"] == "rt-1"
    assert thread_id is not None  # uuid4 generated in memory

    # 3. Second load — same thread_id, data unchanged
    snap2, tid2 = await adapter.load_or_init("s1")
    assert tid2 == thread_id
    assert snap2["pending"]["resume_token"] == "rt-1"

    # 4. round_trip predicate confirms pending is still present
    assert await adapter.round_trip("s1") is True


@pytest.mark.asyncio
async def test_load_or_init_nonexistent_session_returns_empty_snapshot(sqlite_session_factory):
    """A session that has never been persisted returns empty snapshot + empty thread_id."""
    from app.domain.agent.langgraph_nodes.checkpoint_adapter import CheckpointAdapter

    adapter = CheckpointAdapter(session_factory=sqlite_session_factory)
    snapshot, thread_id = await adapter.load_or_init("does-not-exist")
    assert snapshot == {"messages": [], "pending": None}
    assert thread_id == ""


@pytest.mark.asyncio
async def test_round_trip_false_when_no_pending(sqlite_session_factory):
    """round_trip returns False when there is no pending_confirmation."""
    from app.domain.agent.langgraph_nodes.checkpoint_adapter import CheckpointAdapter

    adapter = CheckpointAdapter(session_factory=sqlite_session_factory)

    # Persist a snapshot with no pending
    await adapter.persist(
        session_id="s2",
        snapshot={"messages": [], "pending": None},
    )

    # round_trip should return False
    assert await adapter.round_trip("s2") is False
