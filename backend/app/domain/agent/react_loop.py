"""v0.4 ReAct 循环：agent 推理 + 工具执行。

设计要点：
- 自写循环（不引 LangGraph / LangChain）
- MAX_REACT_ITERATIONS = 5 防无限循环
- 流式 yield SSE 事件（assistant_message / tool_call_start / tool_call_result /
  human_confirmation_required / turn_complete / max_iterations_reached）
- 写类工具抛 HumanConfirmationRequired 暂停循环
- 断点续跑：run_agent_turn_from_checkpoint 从上次 pending_confirmation 继续执行
"""
from __future__ import annotations

import json
from typing import AsyncIterator

from app.core.config import get_settings
from app.core.db import get_session_factory
from app.domain.agent.prompts import AGENT_SYSTEM_PROMPT
from app.domain.agent.tool_executor import ToolExecutor
from app.domain.agent.tools import TOOLS
from app.domain.llm_client import LLMClient
from app.models.orm_v04 import AgentMessageORM
from app.repositories.agent_repo import AgentRepository

MAX_REACT_ITERATIONS = 5


# ===========================================================================
# 消息构建
# ===========================================================================


def build_messages(history: list[dict]) -> list[dict]:
    """把 DB 风格历史转换为 OpenAI chat completion 协议格式。

    输入 history 元素格式：
      {"role": "user"|"assistant"|"tool"|"system", "content": str|None, ...}

    特殊处理：
    - assistant 消息的 tool_calls.arguments 可能是 JSON 字符串（DB 存储），
      要反序列化为 dict（LLM 需要）
    - tool 消息必须带 tool_call_id（OpenAI 协议要求）
    - 系统 prompt 总是作为第一条注入
    """
    out: list[dict] = [{"role": "system", "content": AGENT_SYSTEM_PROMPT}]

    for msg in history:
        role = msg["role"]
        if role == "user":
            out.append({"role": "user", "content": msg["content"]})
        elif role == "assistant":
            asst: dict = {"role": "assistant", "content": msg.get("content")}
            if msg.get("tool_calls"):
                tc_raw = msg["tool_calls"]
                if isinstance(tc_raw, str):
                    tc_raw = json.loads(tc_raw)
                # 兼容两种格式：
                # 1. OpenAI 风格：{id, function: {name, arguments}}
                # 2. 简化风格：{tool, arguments}
                normalized = []
                for tc in tc_raw:
                    if "function" in tc:
                        args = tc["function"]["arguments"]
                        normalized.append({
                            "id": tc.get("id", ""),
                            "type": "function",
                            "function": {
                                "name": tc["function"]["name"],
                                "arguments": json.loads(args)
                                if isinstance(args, str)
                                else args,
                            },
                        })
                    elif "tool" in tc:
                        # 简化风格 → 转换为 OpenAI 风格
                        normalized.append({
                            "id": tc.get("id", ""),
                            "type": "function",
                            "function": {
                                "name": tc["tool"],
                                "arguments": tc["arguments"],
                            },
                        })
                asst["tool_calls"] = normalized
            out.append(asst)
        elif role == "tool":
            out.append({
                "role": "tool",
                "tool_call_id": msg["tool_call_id"],
                "content": msg["content"],
            })
        # 其他 role 忽略（防御性）

    return out


def _orm_to_dict(m: AgentMessageORM) -> dict:
    """ORM 消息转 dict 格式。"""
    return {
        "id": m.id,
        "role": m.role,
        "content": m.content,
        "tool_calls": m.tool_calls,
        "tool_call_id": m.tool_call_id,
    }


# ===========================================================================
# ReAct 主循环
# ===========================================================================


async def run_agent_turn(
    session_id: str,
    user_message: str,
) -> AsyncIterator[dict]:
    """执行一轮 agent 推理 + 行动循环。流式 yield SSE 事件。

    流程：
    1. 加载历史消息
    2. 保存 user 消息
    3. 循环 MAX_REACT_ITERATIONS 次：
       a. 调 LLM (chat_with_tools)
       b. 保存 assistant 消息
       c. yield assistant_message
       d. 如果有 tool_calls：
          - 对每个 tool：yield tool_call_start → 执行（executor） → 保存 tool 消息 → yield tool_call_result
          - 如果抛 HumanConfirmationRequired：yield human_confirmation_required 并暂停
       e. 否则 yield turn_complete 结束
    4. 超过 MAX_ITERATIONS：yield max_iterations_reached
    """
    settings = get_settings()
    llm = LLMClient(settings)
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

    # 3. ReAct 循环
    for _iteration in range(MAX_REACT_ITERATIONS):
        messages = build_messages(history)

        response = await llm.chat_with_tools(messages=messages, tools=TOOLS)
        content = response.get("content")
        tool_calls = response.get("tool_calls") or []

        # 保存 assistant 消息
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
        async with factory() as session:
            repo = AgentRepository(session)
            await repo.create_message(
                session_id=session_id, role="assistant",
                content=content, tool_calls=tc_for_db,
            )

        yield {"event": "assistant_message", "content": content or ""}

        if tool_calls:
            executor = ToolExecutor(session_id)
            should_continue = True
            for tool_call in tool_calls:
                if not should_continue:
                    break
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

                try:
                    result = await executor.execute(tool_name, tool_args)
                except Exception as exc:
                    from app.domain.exceptions import HumanConfirmationRequired

                    if isinstance(exc, HumanConfirmationRequired):
                        yield {
                            "event": "human_confirmation_required",
                            "message_id": exc.message_id,
                            "tool_name": exc.tool_name,
                            "arguments": exc.arguments,
                        }
                        return  # 暂停，等用户确认

                    # 其它异常：包装成错误返回给 LLM，让 LLM 决策
                    err_payload = {"error": f"{type(exc).__name__}: {exc}"}
                    async with factory() as session:
                        repo = AgentRepository(session)
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

                # 成功：保存 tool 消息 + yield result
                async with factory() as session:
                    repo = AgentRepository(session)
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

            # 重新加载历史让下一轮看到 tool 结果
            async with factory() as session:
                repo = AgentRepository(session)
                history_rows = await repo.list_messages(session_id)
            history = [_orm_to_dict(m) for m in history_rows]
        else:
            # LLM 没调用工具 = 最终回答
            yield {"event": "turn_complete"}
            return

    # 4. 达到最大迭代
    yield {
        "event": "max_iterations_reached",
        "message": f"agent 达到最大推理步数 ({MAX_REACT_ITERATIONS})",
    }


# ===========================================================================
# 断点续跑（用户决策要求：不是 MVP）
# ===========================================================================


async def run_agent_turn_from_checkpoint(
    session_id: str,
    checkpoint_message_id: str,
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

    settings = get_settings()
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

    # 6. 继续 ReAct 循环（重新加载历史，让 LLM 基于新 tool 结果继续决策）
    llm = LLMClient(settings)
    async with factory() as session:
        repo = AgentRepository(session)
        history_rows = await repo.list_messages(session_id)
    history = [_orm_to_dict(m) for m in history_rows]

    for _iteration in range(MAX_REACT_ITERATIONS):
        messages = build_messages(history)
        response = await llm.chat_with_tools(messages=messages, tools=TOOLS)
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
        async with factory() as session:
            repo = AgentRepository(session)
            await repo.create_message(
                session_id=session_id, role="assistant",
                content=content, tool_calls=tc_for_db,
            )
        yield {"event": "assistant_message", "content": content or ""}

        if tool_calls:
            should_continue = True
            for tool_call in tool_calls:
                if not should_continue:
                    break
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

                try:
                    result = await executor.execute(tool_name, tool_args)
                except Exception as exc:
                    from app.domain.exceptions import HumanConfirmationRequired

                    if isinstance(exc, HumanConfirmationRequired):
                        yield {
                            "event": "human_confirmation_required",
                            "message_id": exc.message_id,
                            "tool_name": exc.tool_name,
                            "arguments": exc.arguments,
                        }
                        return
                    err_payload = {"error": f"{type(exc).__name__}: {exc}"}
                    async with factory() as session:
                        repo = AgentRepository(session)
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

                async with factory() as session:
                    repo = AgentRepository(session)
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

            async with factory() as session:
                repo = AgentRepository(session)
                history_rows = await repo.list_messages(session_id)
            history = [_orm_to_dict(m) for m in history_rows]
        else:
            yield {"event": "turn_complete"}
            return

    yield {
        "event": "max_iterations_reached",
        "message": f"agent 达到最大推理步数 ({MAX_REACT_ITERATIONS})",
    }