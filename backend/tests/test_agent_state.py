# backend/tests/test_agent_state.py
from langchain_core.messages import HumanMessage
from app.domain.agent.state import AgentState


def test_agent_state_inherits_messages_reducer():
    s: AgentState = {"messages": [], "session_id": "s1"}
    out = AgentState(
        messages=[HumanMessage(content="hi")],
        session_id="s1",
        memory_chunk=None,
        truncation_result=None,
        tool_call_log=[],
    )
    assert hasattr(out, "messages") or "messages" in out
    assert len(out["messages"]) == 1


def test_agent_state_carries_memory_chunk():
    chunk = {"scope": "u1", "items": [{"text": "prior pref", "score": 0.9}]}
    s = AgentState(
        messages=[HumanMessage(content="hi")],
        session_id="s1",
        memory_chunk=chunk,
        truncation_result=None,
        tool_call_log=[],
    )
    assert s["memory_chunk"] == chunk
