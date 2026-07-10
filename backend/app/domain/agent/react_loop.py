"""v0.4 ReAct 循环：agent 推理 + 工具执行。

设计要点：
- 自写循环（30 行核心），不引 LangGraph / LangChain
- MAX_REACT_ITERATIONS = 5 防无限循环
- 流式 yield SSE 事件（assistant_message / tool_call_start / tool_call_result /
  human_confirmation_required / turn_complete / max_iterations_reached）
- 写类工具抛 HumanConfirmationRequired 暂停循环
- 断点续跑：从上次 pending_confirmation 的 message_id 处继续
"""
from __future__ import annotations

import json
from typing import AsyncIterator

from app.domain.agent.prompts import AGENT_SYSTEM_PROMPT

MAX_REACT_ITERATIONS = 5


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
                asst["tool_calls"] = [
                    {
                        "id": tc["id"],
                        "type": "function",
                        "function": {
                            "name": tc["function"]["name"],
                            "arguments": json.loads(tc["function"]["arguments"])
                            if isinstance(tc["function"]["arguments"], str)
                            else tc["function"]["arguments"],
                        },
                    }
                    for tc in tc_raw
                ]
            out.append(asst)
        elif role == "tool":
            out.append({
                "role": "tool",
                "tool_call_id": msg["tool_call_id"],
                "content": msg["content"],
            })
        # 其他 role 忽略（防御性）

    return out


async def run_agent_turn(
    session_id: str,
    user_message: str,
) -> AsyncIterator[dict]:
    """执行一轮 agent 推理 + 行动循环。流式 yield SSE 事件。

    实现见 Task 4.2。
    """
    # 占位 stub，TDD 阶段先用
    yield {"event": "turn_complete"}