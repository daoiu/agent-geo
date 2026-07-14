"""Task 4: SSEBridge byte-identical compatibility test.

Compares react_loop SSE output against SSEBridge replay output.
SKIP until Task 11 (react_graph factory) is complete.
"""
import json

import pytest

from app.domain.agent.react_loop import run_agent_turn  # noqa: F401


@pytest.mark.asyncio
async def test_sse_bridge_byte_identical_to_react_loop(monkeypatch):
    """同一 fixture input:react_loop 输出与 SSEBridge 输出 byte-identical。

    Skipped until Task 11 completes react_graph factory.
    """
    # react_graph not yet available (Task 11) - skip until then
    react_graph = pytest.importorskip("app.domain.agent.react_graph")

    from app.domain.agent.langgraph_nodes.sse_bridge import SSEBridge

    fixture_input = {
        "session_id": "test-1",
        "message": "诊断一下品牌科技感",
    }

    # React_loop 现有路径收集 SSE
    react_chunks: list[bytes] = []
    async for sse in run_agent_turn(**fixture_input):
        # react_loop yields dict, SSEBridge yields bytes - normalize
        sse_bytes = (json.dumps(sse, ensure_ascii=False) + "\n").encode("utf-8")
        react_chunks.append(sse_bytes)

    # SSEBridge 路径产出(replay 模式,react_graph.astream_events → SSEBridge.dispatch)
    sse_chunks: list[bytes] = []
    async for sse in SSEBridge().replay(fixture_input):
        sse_chunks.append(sse)

    # 排除 timestamp 字段后,bytes 必须相等
    def _strip_ts(b: bytes) -> bytes:
        d = json.loads(b)
        d.pop("timestamp", None)
        d.pop("ts", None)
        return json.dumps(d, sort_keys=True).encode()

    assert [_strip_ts(b) for b in react_chunks] == [_strip_ts(b) for b in sse_chunks]
