"""v0.8 LangGraph agent state(spec 2026-07-14-langgraph-react-loop §4.3)。

继承 LangGraph MessagesState 的 add reducer,在每条消息上自动 concat;
项目专属字段(suffix)用于记忆 prepend / 截断可解释 / 工具调用日志。
"""
from __future__ import annotations

from typing import TypedDict

from langchain_core.messages import AnyMessage
from langgraph.graph.message import MessagesState


class AgentState(MessagesState):
    """react_graph 状态 schema。

    继承 MessagesState: `messages` 自动 add reducer + AnyMessage list。
    其余字段是 TypedDict 风格的 suffix,LangGraph 1.x 用 TypedDict/operator.setdefault 自动合并。
    """

    messages: list[AnyMessage]
    session_id: str
    memory_chunk: dict | None
    # T3 — memory_preheat_node 填充;_agent_node 通过 build_messages 拼到 system 末尾。
    memory_index_segment: str | None
    truncation_result: dict | None
    tool_call_log: list[dict]
