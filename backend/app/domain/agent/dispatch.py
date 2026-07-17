"""v0.8 dispatch(spec §10.2)+ ②b orchestrator 灰度(spec agent-orchestrator §6.2.6)。

路由优先级(三个独立灰度 flag):
  agent_orchestrator_enabled=True → run_orchestrated(②b 编排层)
  否则 langgraph_enabled=True      → _run_langgraph_turn(②a 统一图)
  否则                              → _run_react_loop_turn(保留 v0.8 react_loop 后备)

默认全 False 仍走 react_loop,逐级灰度;rollback = 一行 env。
"""
from __future__ import annotations

from collections.abc import AsyncIterator

from app.core.config import get_settings


async def _run_react_loop_turn(session_id: str, message: str) -> AsyncIterator[bytes]:
    """现有 react_loop 路径(沿用,1 个里程碑后删除)。"""
    import json as _json

    from app.domain.agent.react_loop import run_agent_turn as react_impl

    async for evt in react_impl(session_id=session_id, user_message=message):
        yield (_json.dumps(evt, ensure_ascii=False) + "\n").encode("utf-8")


async def _run_langgraph_turn(session_id: str, message: str) -> AsyncIterator[bytes]:
    """LangGraph 路径:react_graph.astream_events → SSEBridge.dispatch。"""
    from app.domain.agent.langgraph_nodes.sse_bridge import SSEBridge

    sse_bridge = SSEBridge()
    async for sse in sse_bridge.replay({"session_id": session_id, "message": message}):
        yield sse


async def run_agent_turn(session_id: str, message: str) -> AsyncIterator[bytes]:
    """api 层调用入口(spec §10.2 / agent-orchestrator §6.2.6)。"""
    settings = get_settings()
    if settings.agent_orchestrator_enabled:
        from app.domain.agent.orchestrator.graph import run_orchestrated

        async for sse in run_orchestrated(session_id, message):
            yield sse
        return
    if settings.langgraph_enabled:
        async for sse in _run_langgraph_turn(session_id, message):
            yield sse
        return
    async for sse in _run_react_loop_turn(session_id, message):
        yield sse
