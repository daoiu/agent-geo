"""Task 8 MemorySnapshotNode RED tests — L2 记忆按 react_loop 既有语义 prepend 到最后一条 user 消息,不进 system."""
from langchain_core.messages import HumanMessage, SystemMessage

from app.domain.agent.langgraph_nodes.memory_snapshot import memory_snapshot_node


def test_memory_snapshot_prepends_to_last_user_message():
    state = {
        "messages": [HumanMessage(content="请诊断"), HumanMessage(content="再问")],
        "session_id": "u1",
        "memory_chunk": {"scope": "u1", "items": [{"text": "prior pref", "score": 0.9}]},
        "truncation_result": None,
        "tool_call_log": [],
    }
    out = memory_snapshot_node(state, runtime=None)
    msgs = out["messages"]
    # 最后一条 user 消息应该被 prepend 记忆
    assert any("prior pref" in str(m.content) for m in msgs)


def test_memory_snapshot_no_op_when_memory_chunk_none():
    state = {
        "messages": [HumanMessage(content="问")],
        "session_id": "u1",
        "memory_chunk": None,
        "truncation_result": None,
        "tool_call_log": [],
    }
    out = memory_snapshot_node(state, runtime=None)
    assert out["messages"] == state["messages"]


def test_memory_snapshot_does_not_inject_into_system():
    state = {
        "messages": [SystemMessage(content="你是 GEO 助手"), HumanMessage(content="问")],
        "session_id": "u1",
        "memory_chunk": {"items": [{"text": "pref", "score": 1.0}]},
        "truncation_result": None,
        "tool_call_log": [],
    }
    out = memory_snapshot_node(state, runtime=None)
    sys_msgs = [m for m in out["messages"] if isinstance(m, SystemMessage)]
    assert all("pref" not in m.content for m in sys_msgs)
