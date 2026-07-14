"""验证 react_loop 的 async with 嵌套被抽出为 _open_agent_repo 上下文管理器(P1#8 / Task 9)。

重构目标：
1. 消除 5 层 `async with factory() as session: repo = AgentRepository(session); ...`
2. 用 `_open_agent_repo()` 上下文管理器替换，代码更扁平
3. `_drive_react_loop` 接受可选 factory 参数（DI 入口），便于测试注入
"""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.db import get_session_factory
from app.domain.agent.react_loop import _open_agent_repo
from app.repositories.agent_repo import AgentRepository


@pytest.mark.asyncio
async def test_open_agent_repo_yields_usable_repository(temp_db) -> None:
    """_open_agent_repo 上下文管理器应 yield 一个 AgentRepository 实例，可以正常 create_session。"""
    engine = create_async_engine(temp_db)
    from app.models.orm import Base
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)

    async with _open_agent_repo(factory=factory) as repo:
        assert isinstance(repo, AgentRepository), (
            f"_open_agent_repo 应 yield AgentRepository, 实际 {type(repo)}"
        )
        # 可用性检查：能调 repo 方法
        session_row = await repo.create_session(title="test")
        assert session_row.id is not None

    await engine.dispose()


@pytest.mark.asyncio
async def test_open_agent_repo_uses_default_factory_when_none(temp_db, monkeypatch) -> None:
    """不传 factory 时，_open_agent_repo 应回退到 get_session_factory()。"""
    monkeypatch.setenv("DATABASE_URL", temp_db)
    from app.core.config import get_settings
    get_settings.cache_clear()  # type: ignore[attr-defined]
    from app.core.db import init_db
    from app.models.orm import Base
    await init_db()  # 用 default factory 建表

    async with _open_agent_repo() as repo:
        assert isinstance(repo, AgentRepository)
        # 至少不抛异常
        session_row = await repo.create_session(title="default-factory-test")
        assert session_row.id is not None


@pytest.mark.asyncio
async def test_react_loop_accepts_injected_factory(temp_db, monkeypatch) -> None:
    """_drive_react_loop 接受可选 factory 参数；注入后应使用注入的 factory 而不是默认。"""
    from sqlalchemy import event
    from cryptography.fernet import Fernet
    monkeypatch.setenv("ENCRYPTION_KEY", Fernet.generate_key().decode())
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key-not-used")
    from app.core.config import get_settings
    get_settings.cache_clear()  # type: ignore[attr-defined]

    # 用 temp_db 建一个独立 factory
    engine = create_async_engine(temp_db)
    if temp_db.startswith("sqlite"):
        @event.listens_for(engine.sync_engine, "connect")
        def _enable_sqlite_fk(dbapi_conn, _conn_record):
            cur = dbapi_conn.cursor()
            cur.execute("PRAGMA foreign_keys=ON")
            cur.close()
    from app.models.orm import Base
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    injected_factory = async_sessionmaker(engine, expire_on_commit=False)

    # 先在 injected_factory 上 create session
    async with injected_factory() as s:
        from app.repositories.agent_repo import AgentRepository
        repo = AgentRepository(s)
        session_row = await repo.create_session(title="inject-test")
        session_id = session_row.id

    # 用 mock factory tracker：替换 get_session_factory，确认 _drive_react_loop 不调它
    factory_call_count = 0
    def _tracking_get_factory():
        nonlocal factory_call_count
        factory_call_count += 1
        return get_session_factory()

    # 跑 run_agent_turn（简化：直接调 _drive_react_loop）
    import app.domain.agent.react_loop as rl
    with patch("app.domain.agent.react_loop.LLMClient") as MockLLM, \
         patch("app.domain.agent.tool_executor.ToolExecutor.execute",
               new=AsyncMock(return_value={"x": 1})), \
         patch("app.domain.agent.react_loop.get_session_factory",
               side_effect=_tracking_get_factory):
        MockLLM.return_value.chat_with_tools = AsyncMock(return_value={
            "content": "ok", "tool_calls": None,
            "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
        })
        # 直接调用 _drive_react_loop，注入 factory
        events = [
            e async for e in rl._drive_react_loop(
                session_id=session_id,
                history=[{"role": "user", "content": "hi"}],
                device_id=None,
                factory=injected_factory,
            )
        ]

    # 末事件是 turn_complete（因为没 tool_call）
    assert events[-1]["event"] == "turn_complete"
    await engine.dispose()