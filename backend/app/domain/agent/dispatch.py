"""v0.8 dispatch(spec §10.2):按 Settings.langgraph_enabled 路由 run_agent_turn。

默认 flag=False 沿用 react_loop,保留 1 个里程碑;
切流 flag=True 后 langgraph 接管(SSEBridge.replay 包 react_graph.astream_events)。
"""
from __future__ import annotations

from collections.abc import AsyncIterator

from app.core.config import get_settings


async def _run_react_loop_turn(session_id: str, message: str) -> AsyncIterator[bytes]:
    """现有 react_loop 路径(沿用,1 个里程碑后删除)。"""
    from app.domain.agent.react_loop import run_agent_turn as react_impl  # type: ignore

    async for sse in react_impl(session_id=session_id, message=message):  # type: ignore
        yield sse


async def _run_langgraph_turn(session_id: str, message: str) -> AsyncIterator[bytes]:
    """LangGraph 路径:react_graph.astream_events → SSEBridge.dispatch。"""
    from app.domain.agent.langgraph_nodes.sse_bridge import SSEBridge

    sse_bridge = SSEBridge()
    async for sse in sse_bridge.replay({"session_id": session_id, "message": message}):
        yield sse


async def run_agent_turn(session_id: str, message: str) -> AsyncIterator[bytes]:
    """api 层调用入口(spec §10.2)。

    根据 Settings.langgraph_enabled 路由到 react_loop 或 langgraph 路径。
    """
    if get_settings().langgraph_enabled:
        async for sse in _run_langgraph_turn(session_id, message):
            yield sse
    else:
        async for sse in _run_react_loop_turn(session_id, message):
            yield sse
