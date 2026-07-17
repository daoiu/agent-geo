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

T4 — metrics 收尾发射:在 turn_complete / interrupt / max_iterations / llm_error
前调 _emit_metrics(state.acc_metrics, ...) + compute_cost(primary, ...),
与 react_loop._drive_react_loop 行为字节级对齐。
"""
from __future__ import annotations

import json
import time
from collections.abc import AsyncIterator
from typing import Any

from langchain_core.runnables.schema import StreamEvent

from app.domain.agent.turn_helpers import _emit_metrics, _new_metrics


def _emit(event_type: str, data: dict) -> bytes:
    """react_loop 现有 SSE 行格式: {"event": event_type, ...data}"""
    payload = {"event": event_type, **data}
    return (json.dumps(payload, ensure_ascii=False) + "\n").encode("utf-8")


class SSEBridge:
    """astream_events → 7 类 SSE 字节输出。

    T4 内部维护 _acc_metrics(从 graph state 中 agent 节点 output.metrics
    累计派生)+ _turn_start(turn_duration_ms 计算)+ _primary_provider(
    compute_cost 计算 USD 成本)。replay() 每次调用创建新实例,状态隔离。
    """

    def __init__(self) -> None:
        self._acc_metrics: dict = _new_metrics()
        self._turn_start: float | None = None
        self._session_id: str | None = None
        self._device_id: str | None = None
        self._primary_provider: Any = None
        self._cost_emitted: bool = False  # 防止重复 emit(turn_complete + 后续 chain_end)

    async def replay(self, fixture_input: dict) -> AsyncIterator[bytes]:
        """测试/双跑使用:把 fixture 喂给 react_graph,产出 7 类 SSE.

        Task 11 完成后可用;Task 11 之前 ImportError/RecursionError 被捕获并映射.
        T4:replay 初始化 _session_id / _device_id / _turn_start / _primary_provider,
        用于 _emit_metrics + compute_cost 收尾调用。
        """
        from app.core.config import get_settings
        from app.core.providers import resolve_providers
        from app.domain.agent.react_graph import build_react_graph

        # T4 — 初始化收尾发射所需的上下文
        self._session_id = fixture_input.get("session_id", "")
        self._device_id = fixture_input.get("device_id")
        self._turn_start = time.perf_counter()
        try:
            settings = get_settings()
            providers = resolve_providers(settings)
            self._primary_provider = providers[0] if providers else None
        except Exception:
            # 配置缺失时静默降级(cost=None)
            self._primary_provider = None

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
            self._emit_metrics_once("max_iterations_reached")
            yield _emit(
                "max_iterations_reached",
                {"message": "agent 达到最大推理步数 (recursion_limit)"},
            )
        except Exception as exc:
            # LLM API 错误（_LLM_TRANSIENT_EXCEPTIONS）或 LangGraph 内部异常
            # 从 graph.astream_events() 传播出来 → 映射为 react_loop 的 llm_error 事件。
            # RecursionError 已在上方单独处理，不会被此处吞掉（子类先捕获）。
            self._emit_metrics_once("llm_error")
            yield _emit(
                "llm_error",
                {
                    "error_type": type(exc).__name__,
                    "message": str(exc),
                    "retryable": True,  # per react_loop 合同（react_loop.py:423）
                },
            )

    async def _dispatch(self, event: StreamEvent) -> AsyncIterator[bytes]:
        ev = event.get("event", "")
        data = event.get("data", {})

        # T4 — 从 on_chain_end 抓取 agent 节点的 metrics output,merge 到 _acc_metrics
        if ev == "on_chain_end":
            output = data.get("output") or {}
            if isinstance(output, dict) and "metrics" in output:
                self._merge_metrics(output["metrics"])

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
            self._emit_metrics_once(f"hitl_{(first.value.get('kind') if first else 'decision')}")
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
            output = data.get("output", {})
            if output and not isinstance(output, str):
                self._emit_metrics_once("turn_complete")
                yield _emit("turn_complete", {})

        # 其余事件(元数据等)不 emit,保持字节级一致

    def _merge_metrics(self, m: dict) -> None:
        """merge agent 节点 output 的 metrics 到 _acc_metrics(后者是字段级 max/累加)。"""
        if not isinstance(m, dict):
            return
        for k in ("iterations", "llm_calls", "tool_calls",
                  "prompt_tokens", "completion_tokens", "total_tokens"):
            v = m.get(k)
            if isinstance(v, (int, float)):
                # 累加而非覆盖:graph state 多次合并时累加正确
                self._acc_metrics[k] = self._acc_metrics.get(k, 0) + v
        if m.get("usage_seen"):
            self._acc_metrics["usage_seen"] = True

    def _compute_cost(self):
        """从 primary provider + 累计 usage 计算 USD cost。"""
        from app.core.providers import compute_cost
        if not self._primary_provider or not self._acc_metrics.get("usage_seen"):
            return None
        return compute_cost(
            self._primary_provider,
            prompt_tokens=self._acc_metrics["prompt_tokens"],
            completion_tokens=self._acc_metrics["completion_tokens"],
        )

    def _emit_metrics_once(self, outcome: str) -> None:
        """收尾时调用一次 _emit_metrics(防止 turn_complete + 后续 chain_end 重复 emit)。"""
        if self._cost_emitted:
            return
        turn_duration_ms = None
        if self._turn_start is not None:
            turn_duration_ms = (time.perf_counter() - self._turn_start) * 1000
        try:
            _emit_metrics(
                self._acc_metrics,
                self._session_id or "",
                self._device_id,
                outcome,
                turn_duration_ms=turn_duration_ms,
                cost_usd=self._compute_cost(),
            )
        except Exception:
            # 发射失败不影响主 SSE 流(react_loop 等价:metrics 失败不影响 turn)
            pass
        self._cost_emitted = True

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
            "memory_index_segment": "",
            "truncation_result": None,
            "tool_call_log": [],
            "metrics": None,
        }