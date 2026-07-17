"""T4 验证:图 metrics 汇总 + 成本 + turn 收尾发射。

react_loop._drive_react_loop 用 _new_metrics / _accumulate 累计 usage,在
turn_complete / max_iterations / HITL 时 _emit_metrics + _compute_turn_cost。

react_graph 需要等价链路:
- _agent_node 把 LLM usage 累计到 state.metrics
- sse_bridge 在 turn_complete / interrupt / max_iterations 收尾时 emit metrics
  + compute_cost(从 primary provider + 累计 usage 计算)

注:cost 计算依赖 primary provider 配置 + compute_cost,本测试聚焦 metrics
累计 + sse_bridge 收尾调用 _emit_metrics 的契约;cost 数值由 compute_cost
模块自身保证正确性,react_loop 路径已通过 parity 测试覆盖。
"""
from __future__ import annotations

import json

import pytest


@pytest.mark.asyncio
async def test_agent_node_returns_metrics_with_usage(monkeypatch, db_session):
    """_agent_node 调 LLM 后,返回值 metrics 字段含累计 usage(llm_calls=1)。"""
    from app.repositories.agent_repo import AgentRepository
    import app.domain.agent.react_graph as rg

    sess = await AgentRepository(db_session).create_session(title="T")
    sid = sess.id

    class _Stub:
        last_call_duration_ms = 0
        primary_provider_name = staticmethod(lambda: "stub")

        async def chat_with_tools(self, messages, tools):
            return {
                "content": "答复",
                "tool_calls": None,
                "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
            }

    monkeypatch.setattr(rg, "LLMClient", _Stub)

    state = {
        "messages": [],
        "session_id": sid,
        "device_id": None,
        "memory_chunk": None,
        "memory_index_segment": "",
        "truncation_result": None,
        "tool_call_log": [],
    }
    out = await rg._agent_node(state, None)

    assert "metrics" in out
    m = out["metrics"]
    assert m["llm_calls"] == 1
    assert m["iterations"] == 1
    assert m["total_tokens"] == 15
    assert m["usage_seen"] is True


@pytest.mark.asyncio
async def test_agent_node_metrics_accumulate_across_calls(monkeypatch, db_session):
    """第二次 _agent_node 调用基于 state['metrics'] 累加,而非覆盖。"""
    from app.repositories.agent_repo import AgentRepository
    import app.domain.agent.react_graph as rg

    sess = await AgentRepository(db_session).create_session(title="T")
    sid = sess.id

    call_count = {"n": 0}

    class _Stub:
        last_call_duration_ms = 0
        primary_provider_name = staticmethod(lambda: "stub")

        async def chat_with_tools(self, messages, tools):
            call_count["n"] += 1
            return {
                "content": f"答复{call_count['n']}",
                "tool_calls": None,
                "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
            }

    monkeypatch.setattr(rg, "LLMClient", _Stub)

    state = {
        "messages": [],
        "session_id": sid,
        "device_id": None,
        "memory_chunk": None,
        "memory_index_segment": "",
        "truncation_result": None,
        "tool_call_log": [],
    }

    out1 = await rg._agent_node(state, None)
    state["metrics"] = out1["metrics"]
    out2 = await rg._agent_node(state, None)

    m = out2["metrics"]
    assert m["llm_calls"] == 2
    assert m["total_tokens"] == 30


@pytest.mark.asyncio
async def test_sse_bridge_dispatch_calls_emit_metrics_on_turn_complete(monkeypatch):
    """sse_bridge._dispatch 在产出 turn_complete 事件前调 _emit_metrics。"""
    from app.domain.agent.langgraph_nodes.sse_bridge import SSEBridge

    emitted: list[dict] = []

    def _fake_emit_metrics(agg, session_id, device_id, outcome, turn_duration_ms=None, cost_usd=None):
        # _emit_metrics 是 sync(turn_helpers._emit_metrics),不是 async
        emitted.append({
            "session_id": session_id,
            "outcome": outcome,
            "llm_calls": agg["llm_calls"],
            "total_tokens": agg["total_tokens"],
        })

    monkeypatch.setattr(
        "app.domain.agent.langgraph_nodes.sse_bridge._emit_metrics",
        _fake_emit_metrics,
    )

    bridge = SSEBridge()
    # T4:sse_bridge 内部累加 state 派生的 metrics(session_id / device_id /
    # metrics 由 graph state 在 astream_events 中提取)
    bridge._session_id = "s1"
    bridge._device_id = None
    bridge._acc_metrics = {
        "iterations": 1, "llm_calls": 1, "tool_calls": 0,
        "prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15,
        "usage_seen": True,
    }

    # 构造 turn_complete 事件(on_chain_end,非 interrupt)
    evt = {"event": "on_chain_end", "data": {"output": {"messages": []}}}
    outs = []
    async for b in bridge._dispatch(evt):
        outs.append(json.loads(b.decode("utf-8")))

    # metrics 在 turn_complete 之前已 emit
    assert any(
        e["outcome"] == "turn_complete"
        and e["llm_calls"] == 1
        and e["total_tokens"] == 15
        for e in emitted
    )
    # turn_complete SSE 也产出
    assert any(o["event"] == "turn_complete" for o in outs)