"""v0.8 SSEBridge(spec §7):把 LangGraph astream_events 输出映射回 react_loop 7 类 SSE 事件。

react_loop 7 类事件:
1. assistant_message
2. tool_call_start
3. tool_call_result
4. human_confirmation_required
5. turn_complete
6. max_iterations_reached
7. llm_error

字节级兼容契约:同一 fixture input 输入,react_loop 现有路径与 SSEBridge 路径
输出(剔除 timestamp 后)byte-identical,以保证前端 SSE 协议零改动。
"""
from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Any

from langchain_core.runnables.schema import StreamEvent


def _emit(event_type: str, data: dict) -> bytes:
    """react_loop 现有 SSE 行格式。"""
    payload = {"type": event_type, **data}
    return (json.dumps(payload, ensure_ascii=False) + "\n").encode("utf-8")


class SSEBridge:
    """astream_events → 7 类 SSE 字节输出。"""

    async def replay(self, fixture_input: dict) -> AsyncIterator[bytes]:
        """测试/双跑使用:把 fixture 喂给 react_graph,产出 7 类 SSE。

        Task 11 完成后可用;Task 11 之前 ImportError。
        """
        from app.domain.agent.react_graph import build_react_graph

        graph = build_react_graph()

        async for event in graph.astream_events(
            self._initial_state(fixture_input),
            config={"configurable": {"thread_id": fixture_input["session_id"]}},
            version="v2",
        ):
            async for sse in self._dispatch(event):
                yield sse

    async def _dispatch(self, event: StreamEvent) -> AsyncIterator[bytes]:
        ev = event.get("event", "")
        data = event.get("data", {})

        if ev == "on_chat_model_stream":
            chunk = data.get("chunk")
            if chunk is not None:
                yield _emit(
                    "assistant_message",
                    {"content": chunk.content if hasattr(chunk, "content") else ""},
                )
        elif ev == "on_tool_start":
            yield _emit(
                "tool_call_start",
                {
                    "name": data.get("name"),
                    "args": data.get("input", {}),
                    "id": data.get("run_id"),
                },
            )
        elif ev == "on_tool_end":
            yield _emit(
                "tool_call_result",
                {
                    "name": data.get("name"),
                    "output": data.get("output"),
                    "id": data.get("run_id"),
                },
            )
        elif ev == "on_chain_end" and "__interrupt__" in (data.get("output") or {}):
            intr = data["output"]["__interrupt__"]
            yield _emit(
                "human_confirmation_required",
                {
                    "tool_call_id": intr[0].value.get("tool_call_id") if intr else None,
                    "args": intr[0].value.get("args", {}) if intr else {},
                    "resume_token": intr[0].id if intr else None,
                },
            )
        # 其余事件(元数据等)不 emit,保持字节级一致

    def _initial_state(self, fixture_input: dict) -> dict:
        from langchain_core.messages import HumanMessage

        return {
            "messages": [HumanMessage(content=fixture_input["message"])],
            "session_id": fixture_input["session_id"],
            "memory_chunk": None,
            "truncation_result": None,
            "tool_call_log": [],
        }
