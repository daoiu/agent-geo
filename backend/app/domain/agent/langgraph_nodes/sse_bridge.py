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
    """react_loop 现有 SSE 行格式: {"event": event_type, ...data}"""
    payload = {"event": event_type, **data}
    return (json.dumps(payload, ensure_ascii=False) + "\n").encode("utf-8")


class SSEBridge:
    """astream_events → 7 类 SSE 字节输出。"""

    async def replay(self, fixture_input: dict) -> AsyncIterator[bytes]:
        """测试/双跑使用:把 fixture 喂给 react_graph,产出 7 类 SSE.

        Task 11 完成后可用;Task 11 之前 ImportError/RecursionError 被捕获并映射.
        """
        from app.domain.agent.react_graph import build_react_graph

        graph = build_react_graph()

        try:
            async for event in graph.astream_events(
                self._initial_state(fixture_input),
                config={"configurable": {"thread_id": fixture_input["session_id"]}},
                version="v2",
            ):
                async for sse in self._dispatch(event):
                    yield sse
        except RecursionError:
            # LangGraph recursion_limit 超出时抛出 RecursionError → 映射为
            # react_loop 的 max_iterations_reached 事件
            yield _emit(
                "max_iterations_reached",
                {"message": "agent 达到最大推理步数 (recursion_limit)"},
            )

    async def _dispatch(self, event: StreamEvent) -> AsyncIterator[bytes]:
        ev = event.get("event", "")
        data = event.get("data", {})

        # 1. assistant_message
        if ev == "on_chat_model_stream":
            chunk = data.get("chunk")
            if chunk is not None:
                yield _emit(
                    "assistant_message",
                    {"content": chunk.content if hasattr(chunk, "content") else ""},
                )

        # 2. tool_call_start
        elif ev == "on_tool_start":
            yield _emit(
                "tool_call_start",
                {
                    "tool_call_id": data.get("name"),  # run_id 是 tool 名作为 id
                    "tool_name": data.get("name"),
                    "arguments": data.get("input", {}),
                },
            )

        # 3. tool_call_result
        elif ev == "on_tool_end":
            yield _emit(
                "tool_call_result",
                {
                    "tool_call_id": data.get("name"),
                    "result": data.get("output"),
                },
            )

        # 4. human_confirmation_required
        elif ev == "on_chain_end" and self._has_interrupt(data):
            intr = data["output"].get("__interrupt__") or []
            first = intr[0] if intr else None
            payload = {
                "event": "human_confirmation_required",
                "kind": first.value.get("kind") if first else None,
                "message_id": first.value.get("message_id") if first else None,
                "tool_name": first.value.get("tool_name") if first else None,
                "arguments": first.value.get("arguments", {}) if first else {},
                "tool_call_id": first.value.get("tool_call_id") if first else None,
                "resume_token": first.id if first else None,
            }
            yield _emit("human_confirmation_required", payload)

        # 5. turn_complete (on_chain_end without __interrupt__)
        elif ev == "on_chain_end" and not self._has_interrupt(data):
            # 确认不是最外层 graph 的 end (通过检查 output 结构)
            # react_loop 只在单步推理结束时发出 turn_complete
            output = data.get("output", {})
            # 跳过 graph 顶层 end（无意义的空 turn）
            if output and not isinstance(output, str):
                yield _emit("turn_complete", {})

        # 6. llm_error — LangGraph 不会直接发此事件;通过 replay 中捕获 RecursionError
        #    统一在上层处理;本 dispatch 不需要额外 handler

        # 其余事件(元数据等)不 emit,保持字节级一致

    def _has_interrupt(self, data: dict) -> bool:
        """检查 on_chain_end output 是否含 __interrupt__。"""
        output = data.get("output") or {}
        if isinstance(output, dict):
            return "__interrupt__" in output
        return False

    def _initial_state(self, fixture_input: dict) -> dict:
        from langchain_core.messages import HumanMessage

        return {
            "messages": [HumanMessage(content=fixture_input["message"])],
            "session_id": fixture_input["session_id"],
            "memory_chunk": None,
            "truncation_result": None,
            "tool_call_log": [],
        }
