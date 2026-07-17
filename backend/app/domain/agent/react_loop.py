"""v0.4 ReAct 循环：agent 推理 + 工具执行。

设计要点：
- 自写循环（不引 LangGraph / LangChain）
- max_react_iterations（来自 Settings）防无限循环，阶段 1 硬编码 7，阶段 2 P1#7（Task 8）提到 Settings
- 流式 yield SSE 事件（assistant_message / tool_call_start / tool_call_result /
  human_confirmation_required / turn_complete / max_iterations_reached）
- 写类工具抛 HumanConfirmationRequired 暂停循环
- 断点续跑：run_agent_turn_from_checkpoint 从上次 pending_confirmation 继续执行

v0.6 P1.6 — L2 跨会话偏好：
- `build_messages` 接受 `memory_index_segment`,拼到 system 末尾
- `_apply_memory_prepend` 在每个 LLM call 前把相关记忆 prepended 到 user 消息
- `_do_extract_after_turn` 在 `turn_complete` 前 fire-and-forget 触发蒸馏
- `_PENDING_EXTRACTS` 持有后台 task 防 GC
"""
from __future__ import annotations

import asyncio
import json
import time
from contextlib import asynccontextmanager
from decimal import Decimal
from typing import AsyncIterator

import structlog
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.core.config import get_settings
from app.core.db import get_session_factory
from app.core.providers import compute_cost, resolve_providers
from app.domain.agent.memory import MemoryService, scope_key
from app.domain.agent.prompts import AGENT_SYSTEM_PROMPT
from app.domain.agent.tool_executor import ToolExecutor
from app.domain.agent.tools import TOOLS
from app.domain.exceptions import _LLM_TRANSIENT_EXCEPTIONS, _TOOL_TRANSIENT_EXCEPTIONS
from app.domain.llm_client import LLMClient

from app.models.orm_v04 import AgentMessageORM
from app.repositories.agent_repo import AgentRepository

# v0.6 P1.4: 5 → 7，留余量给 list → search → create_task。
# v0.6+ P1#7: 此常量已上移到 core/config.py:Settings.max_react_iterations（Task 8），
# 便于 env 覆盖，调用方 get_settings().max_react_iterations。
logger = structlog.get_logger()


@asynccontextmanager
async def _open_agent_repo(
    factory: async_sessionmaker | None = None,
):
    """打开一个 session 并 yield AgentRepository。

    v0.6+ P1#8（Task 9）：替代 ``async with factory() as session: repo = AgentRepository(session)``
    的 5 处重复样板代码。每个 ``async with _open_agent_repo() as repo`` 仍是一次独立事务，
    但消除了 ``repo = AgentRepository(session)`` 这一层嵌套。

    factory 为 None 时回退到 ``get_session_factory()``（默认行为）。
    测试可注入自定义 factory（DI 入口）。
    """
    f = factory if factory is not None else get_session_factory()
    async with f() as session:
        yield AgentRepository(session)


# 8 个共享纯函数已迁到 turn_helpers.py（T1 重构,零行为变化）,
# 下方 import 用于 react_loop 自身调用 + 保持既有导入路径兼容。
from app.domain.agent.turn_helpers import (  # noqa: F401  re-export 保持既有导入路径
    build_messages,
    _accumulate,
    _apply_memory_prepend,
    _do_extract_after_turn,  # T5:仅供测试 monkeypatch,生产路径走 schedule_extract
    _emit_metrics,
    _get_tiktoken_encoder,
    _new_metrics,
    _orm_to_dict,
    _PENDING_EXTRACTS,  # T5:re-export,旧测试 monkeypatch 仍可工作
    _truncate_by_tokens,
    schedule_extract,
)


# _do_extract_after_turn 定义已迁到 turn_helpers.py(T5),通过模块顶部
# ``from app.domain.agent.turn_helpers import _do_extract_after_turn``
# 拿到真函数引用。L293 的 fire-and-forget 调度改走 schedule_extract。


# _new_metrics / _accumulate / _emit_metrics 已迁到 turn_helpers.py（T1）,
# 内部调用与外部 re-export 均通过顶部 import 解析。


# ===========================================================================
# ReAct 主循环
# ===========================================================================


async def _drive_react_loop(
    session_id: str,
    history: list[dict],
    device_id: str | None = None,
    *,
    factory: async_sessionmaker | None = None,
) -> AsyncIterator[dict]:
    """共享 ReAct 循环体。两入口做完各自起点差异后委托到此。

    产出的 SSE 事件流与收敛前逐事件等价。

    v0.6+ P1#8（Task 9）：接受可选 factory 参数（DI 入口）。
    不传则使用 ``get_session_factory()`` 默认 factory。测试可注入自定义 factory。
    """
    settings = get_settings()
    llm = LLMClient(settings)
    f = factory if factory is not None else get_session_factory()
    scope = scope_key(device_id, session_id)

    # v0.6+ P1#22（Task 24）：turn 级别计时 + cost 计算
    turn_start = time.perf_counter()
    providers = resolve_providers(settings)
    primary_provider = providers[0] if providers else None

    def _compute_turn_cost() -> Decimal | None:
        """根据 primary provider + 累计 usage 计算 USD cost。"""
        if not primary_provider or not agg["usage_seen"]:
            return None
        return compute_cost(
            primary_provider,
            prompt_tokens=agg["prompt_tokens"],
            completion_tokens=agg["completion_tokens"],
        )

    # 记忆预热（仍需独立 session，因为用的是 MemoryService 而非 AgentRepository）
    async with f() as session:
        memory_service = MemoryService(session)
        memory_index_segment = await memory_service.build_memory_segment(scope)
        memory_block = await memory_service.load_relevant_memories(scope, history)

    agg = _new_metrics()
    for _iteration in range(settings.max_react_iterations):
        messages = build_messages(
            history,
            memory_index_segment=memory_index_segment,
            window_messages=settings.context_window_messages,
            tool_result_max_chars=settings.tool_result_max_chars,
            tool_result_keep_recent=settings.tool_result_keep_recent,
            token_budget_per_tool_result=settings.token_budget_per_tool_result,
        )
        messages = _apply_memory_prepend(messages, memory_block)

        try:
            response = await llm.chat_with_tools(messages=messages, tools=TOOLS)
        except _LLM_TRANSIENT_EXCEPTIONS as exc:
            # v0.6+ P1#9（Task 10）：LLM 调用失败显式降级为 SSE 事件，
            # 不再让异常穿透导致 SSE 流被切断。前端可看到 llm_error 事件并提示用户重试。
            # 编程错误（AttributeError 等）不捕获，让它向上抛（不被吞）。
            err_type = type(exc).__name__
            logger.warning(
                "llm_call_failed_transient",
                session_id=session_id,
                error_type=err_type,
                message=str(exc),
            )
            yield {
                "event": "llm_error",
                "error_type": err_type,
                "message": str(exc),
                "retryable": True,
            }
            return
        _accumulate(agg, response.get("usage"))
        content = response.get("content")
        tool_calls = response.get("tool_calls") or []

        tc_for_db = None
        if tool_calls:
            tc_for_db = [
                {
                    "id": tc["id"],
                    "function": {
                        "name": tc["function"]["name"],
                        "arguments": json.dumps(tc["function"]["arguments"])
                        if isinstance(tc["function"]["arguments"], dict)
                        else tc["function"]["arguments"],
                    },
                }
                for tc in tool_calls
            ]
        async with _open_agent_repo(factory=f) as repo:
            await repo.create_message(
                session_id=session_id, role="assistant",
                content=content, tool_calls=tc_for_db,
            )

        yield {"event": "assistant_message", "content": content or ""}

        if tool_calls:
            executor = ToolExecutor(session_id)
            for tool_call in tool_calls:
                tool_id = tool_call["id"]
                tool_name = tool_call["function"]["name"]
                tool_args = tool_call["function"]["arguments"]
                if isinstance(tool_args, str):
                    tool_args = json.loads(tool_args)

                yield {
                    "event": "tool_call_start",
                    "tool_call_id": tool_id,
                    "tool_name": tool_name,
                    "arguments": tool_args,
                }
                agg["tool_calls"] += 1

                try:
                    result = await executor.execute(tool_name, tool_args)
                except _TOOL_TRANSIENT_EXCEPTIONS as exc:
                    # v0.6+ P1#15（Task 16）：transient 异常降级为 tool_call_result error,
                    # LLM 看到错误可决定下一步(继续 / 重试 / 改方案)。
                    # 编程错误（ValueError / AttributeError 等）不被捕获,向上抛。
                    err_payload = {"error": f"{type(exc).__name__}: {exc}"}
                    async with _open_agent_repo(factory=f) as repo:
                        await repo.create_message(
                            session_id=session_id, role="tool",
                            content=json.dumps(err_payload, ensure_ascii=False),
                            tool_call_id=tool_id,
                        )
                    yield {
                        "event": "tool_call_result",
                        "tool_call_id": tool_id,
                        "result": err_payload,
                    }
                    continue
                except Exception as exc:
                    # 任意 HITL 类型(decision/input/progress_confirm)都优先识别
                    # yield 对应 kind 的暂停事件后 return 退出。
                    from app.domain.exceptions import HumanConfirmationBase

                    if isinstance(exc, HumanConfirmationBase):
                        _emit_metrics(
                            agg, session_id, device_id, f"hitl_{exc.kind}",
                            turn_duration_ms=(time.perf_counter() - turn_start) * 1000,
                            cost_usd=_compute_turn_cost(),
                        )
                        # 根据 kind 生成不同 SSE event 名称
                        event_name_map = {
                            "decision": "human_confirmation_required",
                            "input": "input_required",
                            "progress_confirm": "progress_confirm",
                        }
                        event_name = event_name_map.get(exc.kind, "human_confirmation_required")
                        payload = {
                            "event": event_name,
                            "kind": exc.kind,
                            "message_id": exc.message_id,
                            "tool_name": exc.tool_name,
                            "arguments": exc.arguments,
                        }
                        # 按 kind 附加额外字段
                        if exc.kind == "input":
                            payload["input_schema"] = exc.input_schema
                            payload["prompt"] = exc.prompt
                        elif exc.kind == "progress_confirm":
                            payload["progress_pct"] = exc.progress_pct
                            payload["eta_seconds"] = exc.eta_seconds
                        yield payload
                        return
                    # 其他编程错误:向上抛,不被吞
                    raise

                async with _open_agent_repo(factory=f) as repo:
                    await repo.create_message(
                        session_id=session_id, role="tool",
                        content=json.dumps(result, ensure_ascii=False),
                        tool_call_id=tool_id,
                    )
                yield {
                    "event": "tool_call_result",
                    "tool_call_id": tool_id,
                    "result": result,
                }

            async with _open_agent_repo(factory=f) as repo:
                history_rows = await repo.list_messages(session_id)
            history = [_orm_to_dict(m) for m in history_rows]
        else:
            # T5 — schedule_extract 封装了 asyncio.create_task + _PENDING_EXTRACTS
            # 防 GC + done 回调移除。sse_bridge 也走同一函数,消除重复。
            schedule_extract(device_id, session_id, history)
            _emit_metrics(
                agg, session_id, device_id, "turn_complete",
                turn_duration_ms=(time.perf_counter() - turn_start) * 1000,
                cost_usd=_compute_turn_cost(),
            )
            yield {"event": "turn_complete"}
            return

    _emit_metrics(
        agg, session_id, device_id, "max_iterations_reached",
        turn_duration_ms=(time.perf_counter() - turn_start) * 1000,
        cost_usd=_compute_turn_cost(),
    )
    yield {
        "event": "max_iterations_reached",
        "message": f"agent 达到最大推理步数 ({settings.max_react_iterations})",
    }


async def run_agent_turn(
    session_id: str,
    user_message: str,
    device_id: str | None = None,
) -> AsyncIterator[dict]:
    """执行一轮 agent 推理 + 行动循环。流式 yield SSE 事件。

    起点差异:加载历史 → 保存 user 消息 → 委托共享循环。
    """
    factory = get_session_factory()

    # 1. 加载历史 + 2. 保存 user 消息
    async with factory() as session:
        repo = AgentRepository(session)
        history_rows = await repo.list_messages(session_id)
        await repo.create_message(
            session_id=session_id, role="user", content=user_message
        )
    history = [_orm_to_dict(m) for m in history_rows] + [
        {"role": "user", "content": user_message}
    ]

    async for evt in _drive_react_loop(session_id, history, device_id):
        yield evt


# ===========================================================================
# 断点续跑（用户决策要求：不是 MVP）
# ===========================================================================


async def run_agent_turn_from_checkpoint(
    session_id: str,
    checkpoint_message_id: str,
    device_id: str | None = None,
) -> AsyncIterator[dict]:
    """从 pending_confirmation 消息处继续执行。

    适用场景：
    1. 用户首次输入"生成文章"
    2. agent 调 generate_article → ToolExecutor 抛 HumanConfirmationRequired（落 pending msg）
    3. ReAct 循环 yield human_confirmation_required 后暂停
    4. 前端弹窗，用户点"确认"
    5. POST /sessions/{sid}/messages/{msg_id}/confirm {approved: true}
    6. 调本函数：
       a. 找到 checkpoint message，解析其 tool_calls[0].arguments
       b. 调 _execute_generate_article_confirmed(args, checkpoint_message_id) → 真正生成预览
       c. 保存 tool 消息（作为该 pending msg 的结果）
       d. 继续 ReAct 循环（重新加载历史 + 调 LLM）

    异常处理：
    - 如果 checkpoint_message_id 不存在或已 resolved：yield error 并退出
    """
    from app.domain.agent.tools import GenerateArticleArgs

    factory = get_session_factory()

    # 1. 找到 checkpoint message
    async with factory() as session:
        repo = AgentRepository(session)
        ckpt_msg = await repo.get_message(checkpoint_message_id)

    if ckpt_msg is None or ckpt_msg.session_id != session_id:
        yield {
            "event": "error",
            "message": f"checkpoint message {checkpoint_message_id} not found",
        }
        return
    if not ckpt_msg.pending_confirmation:
        yield {
            "event": "error",
            "message": f"checkpoint message {checkpoint_message_id} already resolved",
        }
        return

    # 2. 解析 pending message 的 tool_calls，提取 generate_article args
    if not ckpt_msg.tool_calls:
        yield {"event": "error", "message": "no tool_calls in checkpoint message"}
        return
    tc_list = json.loads(ckpt_msg.tool_calls) if isinstance(ckpt_msg.tool_calls, str) else ckpt_msg.tool_calls
    if not tc_list:
        yield {"event": "error", "message": "empty tool_calls in checkpoint message"}
        return

    # 兼容两种格式：OpenAI 风格 (function.name + function.arguments) 或简化风格 (tool + arguments)
    first_tc = tc_list[0]
    if "function" in first_tc:
        # OpenAI 风格
        if first_tc["function"]["name"] != "generate_article":
            yield {
                "event": "error",
                "message": f"checkpoint tool is {first_tc['function']['name']}, expected generate_article",
            }
            return
        args_raw = first_tc["function"]["arguments"]
        if isinstance(args_raw, str):
            args_dict = json.loads(args_raw)
        else:
            args_dict = args_raw
    elif "tool" in first_tc:
        # 简化风格（向后兼容旧数据）
        if first_tc["tool"] != "generate_article":
            yield {
                "event": "error",
                "message": f"checkpoint tool is {first_tc['tool']}, expected generate_article",
            }
            return
        args_dict = first_tc["arguments"]
    else:
        yield {"event": "error", "message": "unrecognized tool_calls format"}
        return

    args = GenerateArticleArgs.model_validate(args_dict)
    # tool_call_id 必须与 assistant 消息的 tool_calls[0].id 一致（OpenAI 协议）。
    # _execute_generate_article 写入时 id=message_id，所以这里用 checkpoint_message_id。
    pending_tool_id = checkpoint_message_id

    # 3. 调 _execute_generate_article_confirmed
    # 注意：confirm_message 已在 API 层 (agent_chat.confirm_action) 调用过，
    # 这里不再重复，否则 idempotent 重复执行（不会出错，但浪费）。
    executor = ToolExecutor(session_id)
    try:
        confirmed_result = await executor._execute_generate_article_confirmed(
            args, checkpoint_message_id
        )
    except NotImplementedError:
        # 占位 stub：完整 ContentWriter 实现在后续集成阶段补
        yield {
            "event": "error",
            "message": "_execute_generate_article_confirmed not yet implemented",
        }
        return
    except Exception as exc:  # noqa: BLE001
        yield {
            "event": "error",
            "message": f"confirmed generation failed: {type(exc).__name__}: {exc}",
        }
        return

    # 5. 保存 tool 消息 + yield result
    async with factory() as session:
        repo = AgentRepository(session)
        await repo.create_message(
            session_id=session_id, role="tool",
            content=json.dumps(confirmed_result, ensure_ascii=False),
            tool_call_id=pending_tool_id,
        )

    yield {
        "event": "tool_call_result",
        "tool_call_id": pending_tool_id,
        "result": confirmed_result,
    }

    # 6. 继续 ReAct 循环（委托共享驱动，基于新 tool 结果继续决策）
    async with factory() as session:
        repo = AgentRepository(session)
        history_rows = await repo.list_messages(session_id)
    history = [_orm_to_dict(m) for m in history_rows]

    async for evt in _drive_react_loop(session_id, history, device_id):
        yield evt