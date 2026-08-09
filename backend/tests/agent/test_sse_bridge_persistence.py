"""SSEBridge.replay 持久化与历史加载测试(Web 多轮对话断点回归)。

修复背景: LangGraph 迁移时丢失了 react_loop.run_agent_turn 的两步——
1. user 消息落库(否则 reload 后消息丢失)
2. 从 DB 加载历史消息(否则多轮上下文丢失)

修复位置: sse_bridge._build_initial_state
"""
from __future__ import annotations

from unittest.mock import patch

import pytest


@pytest.mark.asyncio
async def test_replay_persists_user_message_and_loads_history(db_session):
    """replay 后: user 消息落库;第二轮带历史上下文。"""
    from app.repositories.agent_repo import AgentRepository

    repo = AgentRepository(db_session)
    sess = await repo.create_session(title="持久化测试")
    sid = sess.id

    from app.domain.agent.langgraph_nodes.sse_bridge import SSEBridge

    bridge = SSEBridge()

    # stub graph:不真跑 LLM,直接返回空(事件流为空)
    class _StubGraph:
        def __init__(self):
            self._called_with = None

        async def astream_events(self, initial_state, config=None, version=None):
            self._called_with = initial_state
            if False:
                yield {}  # pragma: no cover — 仅保证 async generator 语义

    stub_graph = _StubGraph()

    with patch(
        "app.domain.agent.react_graph.build_react_graph",
        return_value=stub_graph,
    ):
        _ = [
            ev
            async for ev in bridge.replay(
                {"session_id": sid, "message": "第一轮问题", "device_id": None}
            )
        ]

    # 1. user 消息已落库
    msgs = await repo.list_messages(sid)
    assert len(msgs) == 1
    assert msgs[0].role == "user"
    assert msgs[0].content == "第一轮问题"

    # 2. 第二轮: initial state 应包含历史 user 消息 + 当前消息
    with patch(
        "app.domain.agent.react_graph.build_react_graph",
        return_value=stub_graph,
    ):
        _ = [
            ev
            async for ev in bridge.replay(
                {"session_id": sid, "message": "第二轮问题", "device_id": None}
            )
        ]

    state_msgs = stub_graph._called_with["messages"]
    assert len(state_msgs) == 2  # 历史 user(第一轮)+ 当前 user(第二轮)
    from langchain_core.messages import HumanMessage

    assert isinstance(state_msgs[0], HumanMessage)
    assert state_msgs[0].content == "第一轮问题"
    assert state_msgs[1].content == "第二轮问题"

    # 3. 第二轮后 DB 有 2 条 user 消息
    msgs = await repo.list_messages(sid)
    assert [m.content for m in msgs] == ["第一轮问题", "第二轮问题"]


@pytest.mark.asyncio
async def test_replay_history_includes_assistant_and_tool_messages(db_session):
    """历史中 assistant(tool_calls)/tool 消息正确转成 langchain 消息。"""
    from app.repositories.agent_repo import AgentRepository

    repo = AgentRepository(db_session)
    sess = await repo.create_session(title="历史加载")
    sid = sess.id
    await repo.create_message(session_id=sid, role="user", content="帮我写文章")
    await repo.create_message(
        session_id=sid,
        role="assistant",
        content=None,
        tool_calls=[{
            "id": "tc-1",
            "function": {"name": "generate_article", "arguments": '{"topic": "AI"}'},
        }],
    )
    await repo.create_message(
        session_id=sid, role="tool", content='{"task_id": "t-1"}', tool_call_id="tc-1"
    )

    from app.domain.agent.langgraph_nodes.sse_bridge import SSEBridge

    bridge = SSEBridge()

    class _StubGraph:
        def __init__(self):
            self._called_with = None

        async def astream_events(self, initial_state, config=None, version=None):
            self._called_with = initial_state
            if False:
                yield {}

    stub_graph = _StubGraph()
    with patch(
        "app.domain.agent.react_graph.build_react_graph",
        return_value=stub_graph,
    ):
        _ = [
            ev
            async for ev in bridge.replay(
                {"session_id": sid, "message": "继续", "device_id": None}
            )
        ]

    from langchain_core.messages import AIMessage, ToolMessage

    msgs = stub_graph._called_with["messages"]
    assert len(msgs) == 4  # user + assistant(tool_calls) + tool + 当前 user
    assert isinstance(msgs[0].content, str)
    assert isinstance(msgs[1], AIMessage)
    assert msgs[1].tool_calls[0]["name"] == "generate_article"
    assert msgs[1].tool_calls[0]["args"] == {"topic": "AI"}  # arguments 已 JSON 解析
    assert isinstance(msgs[2], ToolMessage)
    assert msgs[2].tool_call_id == "tc-1"
