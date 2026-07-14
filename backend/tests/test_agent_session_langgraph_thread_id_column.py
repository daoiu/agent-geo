"""Test: agent_sessions.langgraph_thread_id column exists after create_all."""
import sqlite3

import pytest


def test_agent_sessions_has_langgraph_thread_id_column(tmp_path):
    """Verify Base.metadata.create_all creates langgraph_thread_id TEXT NULL."""
    from sqlalchemy import create_engine, text

    # Import all ORM modules so Base.metadata sees AgentSessionORM
    from app.models.orm_v04 import AgentSessionORM  # noqa: F401

    db = tmp_path / "test.db"
    engine = create_engine(f"sqlite:///{db}")
    # Create all tables as defined by current Base.metadata
    from app.models.orm import Base

    Base.metadata.create_all(engine)

    cols = [row[1] for row in engine.connect().execute(text("PRAGMA table_info(agent_sessions)")).fetchall()]
    assert "langgraph_thread_id" in cols, f"Expected langgraph_thread_id in {cols}"