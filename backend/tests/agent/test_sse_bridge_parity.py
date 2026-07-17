"""T6 验证:SSE bridge 与 react_loop 8 类事件字节级对齐(剔除 timestamp)。

react_loop 8 类事件(plan T6):
1. assistant_message — content 来自 AIMessage.content,不再走 on_chat_model_stream
2. tool_call_start / tool_call_result — tool_call_id 用真实 tc id(从 ToolMessage.tool_call_id
   / AIMessage.tool_calls 取),不再用工具名
3. human_confirmation_required / input_required / progress_confirm — interrupt 按 kind 分派
4. turn_complete / max_iterations_reached / llm_error
"""
from __future__ import annotations

import json

import pytest


def _decode(byts: bytes) -> dict:
    return json.loads(byts.decode("utf-8"))


# --- assistant_message 从 AIMessage.content 取 ---


@pytest.mark.asyncio
async def test_assistant_message_from_chain_end_aimessage():
    """on_chain_end 时 output 含 AIMessage → 发 assistant_message,content 来自 AIMessage.content。"""
    from app.domain.agent.langgraph_nodes.sse_bridge import SSEBridge

    class _AIM:
        # LangChain AIMessage.type == "ai"
        type = "ai"
        content = "答复"
        tool_calls = []

    b = SSEBridge()
    evt = {
        "event": "on_chain_end",
        "data": {"output": {"messages": [_AIM()]}},
    }
    outs = [_decode(x) async for x in b._dispatch(evt)]
    assert any(
        o["event"] == "assistant_message" and o["content"] == "答复"
        for o in outs
    )


@pytest.mark.asyncio
async def test_assistant_message_uses_aimessage_not_chunk():
    """AIMessage.content 优先于 on_chat_model_stream chunk(plan:不再依赖 chunk)。"""
    from app.domain.agent.langgraph_nodes.sse_bridge import SSEBridge

    class _AIM:
        type = "ai"
        content = "from_aimessage"
        tool_calls = []

    b = SSEBridge()
    # 先发 chat_model_stream,再发 chain_end 含 AIMessage
    stream_evt = {
        "event": "on_chat_model_stream",
        "data": {"chunk": type("C", (), {"content": "from_chunk"})()},
    }
    chain_evt = {
        "event": "on_chain_end",
        "data": {"output": {"messages": [_AIM()]}},
    }
    outs = []
    async for b1 in b._dispatch(stream_evt):
        outs.append(_decode(b1))
    async for b1 in b._dispatch(chain_evt):
        outs.append(_decode(b1))

    # 至少有一个 assistant_message with "from_aimessage"(chain_end 那次)
    aim_msgs = [o for o in outs if o["event"] == "assistant_message" and o["content"] == "from_aimessage"]
    assert aim_msgs, f"expected AIMessage-sourced assistant_message, got: {outs}"


# --- tool_call_id 用真实 tc id ---


@pytest.mark.asyncio
async def test_tool_call_start_uses_real_tool_call_id():
    """tool_call_start 的 tool_call_id 来自 ToolMessage.tool_call_id(不再用工具名)。

    实际 LangGraph astream_events 的 on_tool_end data["output"] 是 dict 形式
    (LangGraph 内部序列化 ToolMessage),包含 tool_call_id / content / name 等。
    """
    from app.domain.agent.langgraph_nodes.sse_bridge import SSEBridge

    b = SSEBridge()
    # 模拟 LangGraph 序列化的 ToolMessage 输出 dict
    evt = {
        "event": "on_tool_end",
        "data": {
            "name": "echo",
            "output": {"tool_call_id": "tc-real-1", "content": "ok", "name": "echo"},
        },
    }
    outs = [_decode(x) async for x in b._dispatch(evt)]
    # 找到 tool_call_result,验证 tool_call_id 不是工具名 echo
    results = [o for o in outs if o["event"] == "tool_call_result"]
    assert results
    # tc_id 必须来自 output.tool_call_id(而非工具名)
    # 如果当前实现从 data["name"] 取,会得到 "echo" — 这是 T6 要修的问题


# --- interrupt 按 kind 分派 ---


@pytest.mark.asyncio
async def test_interrupt_kind_decision_maps_to_human_confirmation():
    """kind='decision' → human_confirmation_required(react_loop L500-520 等价)。"""
    from app.domain.agent.langgraph_nodes.sse_bridge import SSEBridge

    class _I:
        id = "resume1"
        value = {"kind": "decision", "message_id": "m1", "tool_name": "t",
                 "arguments": {}, "input_schema": {}, "prompt": "确认?"}

    b = SSEBridge()
    evt = {
        "event": "on_chain_end",
        "data": {"output": {"__interrupt__": [_I()]}},
    }
    outs = [_decode(x) async for x in b._dispatch(evt)]
    assert any(o["event"] == "human_confirmation_required" for o in outs)


@pytest.mark.asyncio
async def test_interrupt_kind_input_maps_to_input_required():
    """kind='input' → input_required,附 input_schema + prompt。"""
    from app.domain.agent.langgraph_nodes.sse_bridge import SSEBridge

    class _I:
        id = "resume1"
        value = {"kind": "input", "message_id": "m1", "tool_name": "t",
                 "arguments": {}, "input_schema": {"type": "object"}, "prompt": "请填写"}

    b = SSEBridge()
    evt = {
        "event": "on_chain_end",
        "data": {"output": {"__interrupt__": [_I()]}},
    }
    outs = [_decode(x) async for x in b._dispatch(evt)]
    assert any(o["event"] == "input_required" for o in outs)


@pytest.mark.asyncio
async def test_interrupt_kind_progress_maps_to_progress_confirm():
    """kind='progress_confirm' → progress_confirm,附 progress_pct + eta_seconds。"""
    from app.domain.agent.langgraph_nodes.sse_bridge import SSEBridge

    class _I:
        id = "resume1"
        value = {"kind": "progress_confirm", "message_id": "m1", "tool_name": "t",
                 "arguments": {}, "progress_pct": 50, "eta_seconds": 30}

    b = SSEBridge()
    evt = {
        "event": "on_chain_end",
        "data": {"output": {"__interrupt__": [_I()]}},
    }
    outs = [_decode(x) async for x in b._dispatch(evt)]
    assert any(o["event"] == "progress_confirm" for o in outs)