"""orchestrator 编排：router → 模式 → reflection 重试 → 返回最高分。

spec §6.2.5。

deps 注入点便于单测；默认接真实实现（②a 统一图 + Plan-Execute + Reflection）。
附加 SSE 事件：mode_switch / reflection_score（plan 自检声明"前端可忽略"）。
生产 answer 抽取：按 ②a SSEBridge schema — assistant_message 是 chunked 流,
  RealDeps 内 buffer chunks 累积，turn 结束后 yield 完整 answer（带 _SENTINEL
  前缀表明"已自带 emit，请勿重复 emit assistant_message"）。
"""
from __future__ import annotations

import json
from collections.abc import AsyncIterator

import structlog

from app.core.config import get_settings
from app.domain.agent.orchestrator.reflection import pick_best, score_answer, should_retry
from app.domain.agent.orchestrator.router import MODE_PLAN, choose_mode

logger = structlog.get_logger()

# 生产路径下 _RealDeps.react_runner 用此前缀告诉 orchestrator "已自带 SSE 透传，请勿重复 emit assistant_message"
_SSE_ALREADY_EMITTED = "_ORCH_SSE_ALREADY_EMITTED_"


def _emit(event: str, data: dict) -> bytes:
    return (json.dumps({"event": event, **data}, ensure_ascii=False) + "\n").encode("utf-8")


class _RealDeps:
    """默认真实依赖（生产路径）。

    react_runner：调 ②a _run_langgraph_turn，透传 SSE 字节，buffer chunks 累积答案；
                 turn 结束 yield 完整 answer（带 sentinel 避免 orchestrator 重复 emit）。
    plan_runner：MVP1 委托 react_runner 作执行器载体；plan_execute 步骤调用走 ReAct 子图，
                 后续可接更细粒度的步骤执行器。
    reflector：调 reflection.score_answer（spec §6.2.3）。
    """

    def __init__(self):
        from app.domain.llm_client import LLMClient

        self.llm = LLMClient(get_settings())

    async def react_runner(self, session_id: str, message: str, critique=None):
        from app.domain.agent.dispatch import _run_langgraph_turn

        msg = message if not critique else f"{message}\n\n[改进要求]{critique}"
        collected: list[str] = []
        async for sse in _run_langgraph_turn(session_id, msg):
            yield ("sse", sse)
            # 按 ②a SSE schema 解 chunked assistant_message
            try:
                obj = json.loads(sse.decode("utf-8").rstrip("\n"))
            except (json.JSONDecodeError, UnicodeDecodeError):
                continue
            if isinstance(obj, dict) and obj.get("event") == "assistant_message":
                collected.append(str(obj.get("content", "")))
        yield ("answer", _SSE_ALREADY_EMITTED + "".join(collected))

    async def plan_runner(self, session_id: str, message: str, critique=None):
        # MVP1：Plan-Execute 步骤复用 ReAct 子图作 executor 载体；步骤内细化（tool_hint）
        # 待后续 plan_execute 接线。
        async for kind, payload in self.react_runner(session_id, message, critique):
            yield (kind, payload)

    async def reflector(self, query, answer, trace, llm):
        return await score_answer(query, answer, trace, llm)


async def run_orchestrated(
    session_id: str,
    message: str,
    hint: str | None = None,
    deps=None,
) -> AsyncIterator[bytes]:
    """②b 编排入口。

    流程：choose_mode → 跑模式 → reflection 打分 → <min_score 且有余额则带 critique 重试
          → 返回最高分那次。附加发 mode_switch / reflection_score 事件。
    """
    settings = get_settings()
    deps = deps or _RealDeps()

    mode = choose_mode(message, hint=hint)
    yield _emit("mode_switch", {"mode": mode})

    runner = deps.plan_runner if mode == MODE_PLAN else deps.react_runner
    attempts: list[tuple[float, str]] = []
    critique = None
    attempt_no = 0

    while True:
        attempt_no += 1
        answer = ""
        async for kind, payload in runner(session_id, message, critique):
            if kind == "sse":
                yield payload  # 透传底层 SSE
            elif kind == "answer":
                if payload.startswith(_SSE_ALREADY_EMITTED):
                    # 生产路径下 ②a chunks 已 emit，我们只缓存最终答案，不再 emit
                    answer = payload[len(_SSE_ALREADY_EMITTED):]
                else:
                    answer = payload
                    yield _emit("assistant_message", {"content": answer})

        if not settings.reflection_enabled:
            return

        result = await deps.reflector(message, answer, "", deps.llm)
        attempts.append((result.score, answer))
        yield _emit(
            "reflection_score",
            {"score": result.score, "critique": result.critique, "attempt": attempt_no},
        )

        if not should_retry(
            result,
            attempts_done=attempt_no,
            min_score=settings.reflection_min_score,
            max_retries=settings.reflection_max_retries,
        ):
            break
        critique = result.critique

    best = pick_best(attempts)
    # 若最高分不是最后一次（低分用尽），补发一次最终答案给前端
    if best and (not attempts or best != attempts[-1][1]):
        yield _emit("assistant_message", {"content": best})
    yield _emit("turn_complete", {})
