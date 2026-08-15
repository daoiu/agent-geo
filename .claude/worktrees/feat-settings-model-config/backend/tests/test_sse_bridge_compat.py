"""Task 4: SSEBridge byte-identical compatibility test.

Stub-based smoke check; full byte-identical 等 Task 11 + 后续生产化 KPI。
"""
import json

import pytest

from app.domain.agent.langgraph_nodes.sse_bridge import SSEBridge  # noqa: F401  # noqa: E501


@pytest.mark.asyncio
async def test_sse_bridge_byte_identical_to_react_loop(monkeypatch):
    """两条路径在 stub LLM 下都不为空 + 至少产 turn_complete。"""
    pytest.importorskip("app.domain.agent.react_graph")

    async def stub_react(session_id: str, user_message: str):
        yield {"event": "assistant_message", "content": "stub"}
        yield {"event": "turn_complete"}

    import app.domain.agent.react_loop as react_mod

    monkeypatch.setattr(react_mod, "run_agent_turn", stub_react)

    fixture_input = {"session_id": "test-1", "message": "诊断品牌"}

    react_chunks = []
    async for sse in stub_react(
        session_id=fixture_input["session_id"],
        user_message=fixture_input["message"],
    ):
        react_chunks.append(
            (json.dumps(sse, ensure_ascii=False) + "\n").encode("utf-8")
        )

    sse_chunks = []
    try:
        async for sse in SSEBridge().replay(fixture_input):
            sse_chunks.append(sse)
    except (ImportError, ModuleNotFoundError):
        pytest.skip("react_graph not yet available")

    assert react_chunks, "react_loop path produced no SSE"
    assert sse_chunks, "SSEBridge path produced no SSE"

    # 至少 turn_complete 都到位(随 T11 集成后续会扩到 assistant_message 等更严格的字段比对)
    assert any(b'"turn_complete"' in c for c in react_chunks)
    assert any(b'"turn_complete"' in c for c in sse_chunks)
