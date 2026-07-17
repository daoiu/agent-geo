"""v0.8 dispatch(spec §10.2)+ ②b orchestrator 灰度(spec agent-orchestrator §6.2.6)。

②a Agent 路径统一到 LangGraph(2026-07-17 计划):LangGraph 是唯一
agent 执行路径。react_loop 驱动路径已删除(详见 plan Task 10)。

路由优先级(单一灰度 flag):
  agent_orchestrator_enabled=True → run_orchestrated(②b 编排层)
  否则                              → _run_langgraph_turn(②a 唯一图)

rollback = 一行 env(关闭 orchestrator_enabled)。
"""
from __future__ import annotations

from collections.abc import AsyncIterator

from app.core.config import get_settings


async def _run_langgraph_turn(session_id: str, message: str) -> AsyncIterator[bytes]:
    """LangGraph 路径:react_graph.astream_events → SSEBridge.dispatch。

    ②a 唯一 agent 执行路径(react_loop 驱动已删除,plan Task 10)。
    """
    from app.domain.agent.langgraph_nodes.sse_bridge import SSEBridge

    sse_bridge = SSEBridge()
    async for sse in sse_bridge.replay({"session_id": session_id, "message": message}):
        yield sse


async def run_agent_turn(session_id: str, message: str) -> AsyncIterator[bytes]:
    """api 层调用入口(spec §10.2 / agent-orchestrator §6.2.6)。

    ②a 之后唯一两路径:LangGraph(默认) / Orchestrator(②b 灰度)。
    react_loop 驱动已删除(plan Task 10)。
    """
    settings = get_settings()
    if settings.agent_orchestrator_enabled:
        from app.domain.agent.orchestrator.graph import run_orchestrated

        async for sse in run_orchestrated(session_id, message):
            yield sse
        return
    async for sse in _run_langgraph_turn(session_id, message):
        yield sse