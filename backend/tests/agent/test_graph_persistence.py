"""T2 验证:react_graph 的 _agent_node / _tool_node 在执行后把消息落库。

DB 持久化是 react_loop 已具备的能力,react_graph 路径需要补齐以保证两路径
行为字节级对齐(plan Task 2)。

测试设计:不依赖真实 LLM,直接调用 _agent_node / _tool_node,patch AgentRepository
拦截 create_message 调用,验证调用参数正确。
"""
from __future__ import annotations

import os
import tempfile
from collections.abc import AsyncGenerator

import pytest
import pytest_asyncio
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

import app.domain.agent.react_graph as rg


@pytest_asyncio.fixture
async def tmp_session_factory() -> AsyncGenerator[object, None]:
    """最小 in-memory SQLite session factory(供 _agent_node / _tool_node 落库使用)。

    plan Task 2 要求:若 conftest 已有工厂 fixture 则复用,否则新建。本测试独立
    维护一个最小 fixture,不污染既有 db_session(那个 fixture 创建完整 schema,
    而我们只需要 AgentMessageORM 表 + 测试 patch AgentRepository)。
    """
    from sqlalchemy import event
    from app.models import orm as _orm_v01  # noqa: F401
    try:
        from app.models import orm_v04 as _orm_v04  # noqa: F401
    except ImportError:
        pass
    from app.models.orm import Base

    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    engine = create_async_engine(f"sqlite+aiosqlite:///{path}")

    @event.listens_for(engine.sync_engine, "connect")
    def _fk(dbapi_conn, _):  # noqa: ANN001
        cur = dbapi_conn.cursor()
        cur.execute("PRAGMA foreign_keys=ON")
        cur.close()

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    factory = async_sessionmaker(engine, expire_on_commit=False)
    yield factory

    await engine.dispose()
    for _ in range(5):
        if not os.path.exists(path):
            break
        try:
            os.remove(path)
            break
        except PermissionError:
            import time
            time.sleep(0.1)


@pytest.mark.asyncio
async def test_agent_node_persists_assistant(monkeypatch, tmp_session_factory):
    """_agent_node 调 LLM 后,落一条 role='assistant' 消息(无 tool_calls 时)。"""
    import app.domain.agent.react_graph as rg_mod

    saved: list[dict] = []

    class _Repo:
        def __init__(self, _session):
            pass

        async def create_message(self, **kw):
            saved.append(kw)
            return None

    monkeypatch.setattr(rg_mod, "AgentRepository", _Repo)
    monkeypatch.setattr(rg_mod, "get_session_factory", lambda: tmp_session_factory)

    # stub LLM 返回纯文本
    class _Stub:
        last_call_duration_ms = 0
        primary_provider_name = staticmethod(lambda: "stub")

        async def chat_with_tools(self, messages, tools):
            return {"content": "答复", "tool_calls": None, "usage": None}

    monkeypatch.setattr(rg_mod, "LLMClient", _Stub)

    state = {
        "messages": [HumanMessage(content="hi")],
        "session_id": "s1",
        "device_id": None,
        "memory_chunk": None,
        "truncation_result": None,
        "tool_call_log": [],
    }
    out = await rg_mod._agent_node(state, None)

    # 1) 返回 AIMessage
    assert isinstance(out["messages"][0], AIMessage)
    assert out["messages"][0].content == "答复"
    # 2) 落库了一条 assistant 消息
    assert any(k.get("role") == "assistant" for k in saved)
    assert saved[-1]["content"] == "答复"


@pytest.mark.asyncio
async def test_tool_node_persists_tool_message(monkeypatch, tmp_session_factory):
    """_tool_node 工具执行后,落 role='tool' 消息(tool_call_id 真实)。"""
    import app.domain.agent.react_graph as rg_mod

    saved: list[dict] = []

    class _Repo:
        def __init__(self, _session):
            pass

        async def create_message(self, **kw):
            saved.append(kw)
            return None

    monkeypatch.setattr(rg_mod, "AgentRepository", _Repo)
    monkeypatch.setattr(rg_mod, "get_session_factory", lambda: tmp_session_factory)

    # mock ToolExecutor 返回固定结果(在 _tool_node 函数体内 import,
    # patch 必须走 tool_executor 模块而非 react_graph 顶层)
    class _TE:
        def __init__(self, session_id):
            self.session_id = session_id

        async def execute(self, name, args):
            return {"echo": args}

    import app.domain.agent.tool_executor as te_mod
    monkeypatch.setattr(te_mod, "ToolExecutor", _TE)

    state = {
        "messages": [
            AIMessage(
                content="",
                tool_calls=[{"id": "tc-1", "name": "echo", "args": {"x": 1}}],
            )
        ],
        "session_id": "s2",
        "device_id": None,
        "memory_chunk": None,
        "truncation_result": None,
        "tool_call_log": [],
    }
    out = await rg_mod._tool_node(state, None)

    # 1) 返回 ToolMessage
    assert isinstance(out["messages"][0], ToolMessage)
    # 2) 落库一条 tool 消息,tool_call_id 真实
    tool_msgs = [k for k in saved if k.get("role") == "tool"]
    assert tool_msgs, "expected a tool message to be persisted"
    assert tool_msgs[-1]["tool_call_id"] == "tc-1"