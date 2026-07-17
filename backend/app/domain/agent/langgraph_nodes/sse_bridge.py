"""v0.8 SSEBridge(spec §7):把 LangGraph astream_events 输出映射到 8 类 SSE 事件。

CR-5:react_loop 时期 SSE 事件为 7 类(T6 实施时实际只数 7);T6 增加
input_required + progress_confirm 两个 HITL kind,react_graph 路径实际产出
8 类事件。本 docstring 已同步。

8 类事件:
1. assistant_message
2. tool_call_start
3. tool_call_result
4. human_confirmation_required   (HITL kind='decision')
5. input_required                (HITL kind='input',附 input_schema+prompt)
6. progress_confirm              (HITL kind='progress_confirm',附 progress_pct+eta_seconds)
7. turn_complete
8. max_iterations_reached
9. llm_error

字节级兼容契约:同一 fixture input 输入,react_loop 路径(历史,已删)与
SSEBridge 路径输出(剔除 timestamp 后)byte-identical,以保证前端 SSE 协议
零改动。

T4 — metrics 收尾发射:在 turn_complete / interrupt / max_iterations / llm_error
前调 _emit_metrics(state.acc_metrics, ...) + compute_cost(primary, ...),
与 react_loop._drive_react_loop 行为字节级对齐。

CR-5:replay() 方法在 T9 parity 双跑使用,T10 删 react_loop 后已无生产用途,
但保留作为评测/调试入口。详见 docstring。
"""
from __future__ import annotations

import json
import time
from collections.abc import AsyncIterator
from typing import Any

from langchain_core.runnables.schema import StreamEvent

from app.domain.agent.turn_helpers import (
    _emit_metrics,
    _new_metrics,
    langchain_message_content,
    langchain_message_to_dict,
    schedule_extract,
)


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
        """测试/评测使用:把 fixture 喂给 react_graph,产出 8 类 SSE 字节流。

        历史:T9 parity 双跑期间 react_loop vs langgraph 对照用。
        CR-5:T10 删 react_loop 后已无生产用途;evals/runner.py --compare
        改为 LangGraph 单路径自检(不再调 react_loop)。本方法保留供评测
        框架 / 调试 / ad-hoc fixture 重放使用,不应用于生产请求路径。

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

        # 1. assistant_message — T6:不再依赖 on_chat_model_stream;改在 on_chain_end
        # 时从最后一条 AIMessage 取 content(react_loop 单事件 + 完整 content 等价)
        # 同一 on_chain_end 事件也 yield turn_complete(react_loop 等价:turn_complete
        # 是 turn 收尾单事件;assistant_message 先出,turn_complete 后出)
        if ev == "on_chain_end" and not self._has_interrupt(data):
            output = data.get("output") or {}
            msgs = output.get("messages") if isinstance(output, dict) else None
            if msgs:
                last_ai = None
                for m in msgs:
                    role = (
                        getattr(m, "type", None)
                        if not isinstance(m, dict)
                        else m.get("role")
                    )
                    if role in ("ai", "assistant"):
                        last_ai = m
                if last_ai is not None:
                    yield _emit(
                        "assistant_message",
                        {"content": langchain_message_content(last_ai) or ""},
                    )

            # T5 — turn_complete 前 fire-and-forget 触发记忆蒸馏 + 收尾 emit metrics
            if output and not isinstance(output, str):
                history = self._history_from_output(output)
                if history is not None:
                    schedule_extract(self._device_id, self._session_id or "", history)
                self._emit_metrics_once("turn_complete")
                yield _emit("turn_complete", {})

        # 2. tool_call_start — T6:tool_call_id 暂从 on_chain_end 时 AIMessage.tool_calls
        # 取(节点级);on_tool_start 仍用 name 占位,real id 在 tool_call_result 时再校准
        elif ev == "on_tool_start":
            yield _emit(
                "tool_call_start",
                {
                    "tool_call_id": data.get("name"),  # 占位:真 id 见 tool_call_result
                    "tool_name": data.get("name"),
                    "arguments": data.get("input", {}),
                },
            )

        # 3. tool_call_result — T6:tool_call_id 来自 output["tool_call_id"]
        # (LangGraph 序列化的 ToolMessage dict),不再用工具名
        elif ev == "on_tool_end":
            output = data.get("output") or {}
            real_tc_id = None
            if isinstance(output, dict):
                real_tc_id = output.get("tool_call_id")
            elif hasattr(output, "tool_call_id"):
                real_tc_id = output.tool_call_id
            yield _emit(
                "tool_call_result",
                {
                    "tool_call_id": real_tc_id or data.get("name"),
                    "result": output if isinstance(output, (str, int, float, list, dict, bool, type(None))) else str(output),
                },
            )

        # 4. human_confirmation_required / input_required / progress_confirm
        # T6:interrupt 按 kind 分派(react_loop L500-520 等价)
        elif ev == "on_chain_end" and self._has_interrupt(data):
            intr = data["output"].get("__interrupt__") or []
            first = intr[0] if intr else None
            val = (first.value if first else {}) or {}
            kind = val.get("kind") or "decision"
            self._emit_metrics_once(f"hitl_{kind}")

            if kind == "input":
                payload = {
                    "event": "input_required",
                    "kind": "input",
                    "message_id": val.get("message_id"),
                    "tool_name": val.get("tool_name"),
                    "arguments": val.get("arguments", {}),
                    "tool_call_id": val.get("tool_call_id"),
                    "input_schema": val.get("input_schema", {}),
                    "prompt": val.get("prompt", ""),
                    "resume_token": first.id if first else None,
                }
                yield _emit("input_required", payload)
            elif kind == "progress_confirm":
                payload = {
                    "event": "progress_confirm",
                    "kind": "progress_confirm",
                    "message_id": val.get("message_id"),
                    "tool_name": val.get("tool_name"),
                    "arguments": val.get("arguments", {}),
                    "tool_call_id": val.get("tool_call_id"),
                    "progress_pct": val.get("progress_pct"),
                    "eta_seconds": val.get("eta_seconds"),
                    "resume_token": first.id if first else None,
                }
                yield _emit("progress_confirm", payload)
            else:
                # kind='decision' 或默认
                payload = {
                    "event": "human_confirmation_required",
                    "kind": "decision",
                    "message_id": val.get("message_id"),
                    "tool_name": val.get("tool_name"),
                    "arguments": val.get("arguments", {}),
                    "tool_call_id": val.get("tool_call_id"),
                    "resume_token": first.id if first else None,
                }
                yield _emit("human_confirmation_required", payload)

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

    def _history_from_output(self, output: dict) -> list[dict] | None:
        """从 agent 节点 output 提取 messages,转 dict-style 给 schedule_extract。

        CR-1:复用 turn_helpers.langchain_message_to_dict 替代内联实现。
        """
        msgs = output.get("messages") if isinstance(output, dict) else None
        if not msgs:
            return None
        return [langchain_message_to_dict(m) for m in msgs]

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