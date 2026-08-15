"""Task 11 react_graph 工厂 — 整合 4 个自定义 node + 手写 StateGraph。

mock LLMClient 避免真实 API 调用。
"""
import pytest
from langchain_core.messages import AIMessage, HumanMessage

import app.domain.agent.react_graph as rg


@pytest.fixture
def stub_llm(monkeypatch):
    """Stub LLMClient.chat_with_tools 返回简单字符串回复(无 tool_calls)。"""

    async def fake_chat_with_tools(messages, tools):
        return {"content": "stubbed response", "tool_calls": None}

    class _StubLLM:
        last_call_duration_ms = 0
        primary_provider_name = staticmethod(lambda: "stub")

        async def chat_with_tools(self, messages, tools):
            return await fake_chat_with_tools(messages, tools)

    # Patch `LLMClient` import inside react_graph via the runtime lookup
    monkeypatch.setattr(rg, "LLMClient", _StubLLM)
    return _StubLLM()


def test_build_react_graph_returns_compiled_graph():
    g = rg.build_react_graph()
    assert hasattr(g, "astream_events")
    assert hasattr(g, "invoke")
    assert hasattr(g, "ainvoke")


@pytest.mark.asyncio
async def test_react_graph_ainvoke_with_simple_message(monkeypatch):
    """Stub LLM 返回纯文本,react_graph 单步完成 → output 含至少一条 AIMessage。"""
    import app.domain.agent.react_graph as rg
    import app.domain.agent.langgraph_nodes.policy as policy_mod

    class _StubLLM:
        last_call_duration_ms = 0
        primary_provider_name = staticmethod(lambda: "stub")

        async def chat_with_tools(self, messages, tools):
            return {"content": "stubbed response", "tool_calls": None}

    monkeypatch.setattr(rg, "LLMClient", _StubLLM)

    out = await rg.build_react_graph().ainvoke(
        {
            "messages": [HumanMessage(content="hi")],
            "session_id": "test-graph-1",
            "memory_chunk": None,
            "truncation_result": None,
            "tool_call_log": [],
        },
        config={"configurable": {"thread_id": "test-graph-1"}},
    )
    msgs = out["messages"]
    assert len(msgs) >= 1
    assert any(isinstance(m, AIMessage) for m in msgs)
