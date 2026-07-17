"""L2 记忆预热节点(T3)。

react_loop._drive_react_loop 在循环开始前一次性预热:
- MemoryService.build_memory_segment(scope) → system 段末尾拼入的索引
- MemoryService.load_relevant_memories(scope, history) → user 消息 prepend 的关联记忆

react_graph 需要等价节点:在 graph 进入 agent 前填充 state.memory_index_segment +
state.memory_chunk,与 react_loop 路径行为字节级对齐。

降级:异常时返回空字段,不阻塞主流程(react_loop 等价行为)。

CR-1:消息转换复用 turn_helpers.langchain_message_to_dict(消除 sse_bridge 重复)。
"""
from __future__ import annotations

import structlog

from app.core.db import get_session_factory
from app.domain.agent.memory import MemoryService, scope_key
from app.domain.agent.turn_helpers import langchain_message_to_dict

logger = structlog.get_logger()


async def memory_preheat_node(state, runtime) -> dict:
    """填充 state.memory_chunk 与 memory_index_segment。

    输入:state 含 session_id / device_id / messages(可选)
    输出:{memory_chunk: dict|None, memory_index_segment: str}
    """
    session_id = state.get("session_id", "")
    device_id = state.get("device_id")
    scope = scope_key(device_id, session_id)
    history = [langchain_message_to_dict(m) for m in state.get("messages", [])]
    try:
        async with get_session_factory()() as session:
            svc = MemoryService(session)
            seg = await svc.build_memory_segment(scope)
            chunk = await svc.load_relevant_memories(scope, history)
        return {"memory_index_segment": seg, "memory_chunk": chunk}
    except Exception as e:  # noqa: BLE001
        logger.warning(
            "memory_preheat_failed",
            session_id=session_id,
            error=str(e),
        )
        return {"memory_index_segment": "", "memory_chunk": None}