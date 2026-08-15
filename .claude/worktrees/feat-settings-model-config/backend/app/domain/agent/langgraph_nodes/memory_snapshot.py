"""v0.8 MemorySnapshotNode(spec §4.2.3 + §8.1):react_graph 内 L2 记忆 prepend。

严格保留 react_loop 既有 L2 prepend 语义:
- 把 memory_chunk 内容拼到最后一条 user 消息之前(NOT 进 system)
- 若 memory_chunk 为 None / 空则 no-op
- 不重写 react_loop 既有 _apply_memory_prepend(那是 react_loop.py 模块内私有 helper,处理 dict-style)

实现差异 vs react_loop._apply_memory_prepend:
- react_loop 处理 LangChain BaseMessage;本 node 处理 LangGraph state TypedDict 里的 `messages`
- prepend 位置:react_loop 拼第一个 user;本 node 拼最后一个 user(brief 明确要求)
"""
from __future__ import annotations

from typing import TypedDict


def _format_memory_block(chunk: dict) -> str:
    """把 memory_chunk dict 格式化为可 prepend 的字符串。

    format:每条 item 一行,kv: `<text>`(0.9 score)
    """
    items = chunk.get("items") or []
    if not items:
        return ""
    lines = []
    for it in items:
        text = it.get("text") if isinstance(it, dict) else str(it)
        if not text:
            continue
        score = it.get("score") if isinstance(it, dict) else None
        suffix = f" (score={score:.2f})" if isinstance(score, (int, float)) else ""
        lines.append(f"- {text}{suffix}")
    return "L2 memory:\n" + "\n".join(lines)


def memory_snapshot_node(state: TypedDict, runtime) -> dict:
    """Prepend memory_chunk 到最后一条 user 消息。

    Returns:
        dict: LangGraph 状态合并。`messages` 总是返回(保持 messages 字段不会被 reducer 跳过的语义)。
        如果不需要任何修改,返回原 messages 列表(不创建新对象)。
    """
    from langchain_core.messages import HumanMessage  # 延迟,避免 import 周期

    messages = list(state["messages"])
    chunk = state.get("memory_chunk")
    if not chunk or not isinstance(chunk, dict):
        return {"messages": state["messages"]}

    memory_text = _format_memory_block(chunk)
    if not memory_text:
        return {"messages": state["messages"]}

    # 找最后一条 user 消息(HumanMessage)
    last_user_idx = None
    for i in range(len(messages) - 1, -1, -1):
        if isinstance(messages[i], HumanMessage):
            last_user_idx = i
            break
    if last_user_idx is None:
        return {"messages": state["messages"]}

    original = messages[last_user_idx].content
    messages[last_user_idx] = HumanMessage(content=f"{memory_text}\n\n{original}")

    return {"messages": messages}
