"""Task 12 dispatch — Settings.langgraph_enabled 路由 run_agent_turn。"""
import pytest

from app.core.config import get_settings
from app.domain.agent.dispatch import run_agent_turn


@pytest.mark.asyncio
async def test_dispatch_routes_to_react_loop_when_flag_false(monkeypatch):
    """flag=False → 走 react_loop 既有路径。"""
    from app.domain.agent import dispatch as dispatch_module
    monkeypatch.setattr(get_settings(), "langgraph_enabled", False, raising=False)

    called = {"path": None}

    async def fake_react_turn(session_id, message):
        called["path"] = "react_loop"
        yield b'{"event":"turn_complete"}\n'

    async def fake_langgraph_turn(session_id, message):
        called["path"] = "langgraph"
        yield b'{"event":"turn_complete"}\n'

    monkeypatch.setattr(dispatch_module, "_run_react_loop_turn", fake_react_turn)
    monkeypatch.setattr(dispatch_module, "_run_langgraph_turn", fake_langgraph_turn)

    out = []
    async for sse in run_agent_turn(session_id="t1", message="hi"):
        out.append(sse)
    assert called["path"] == "react_loop"
    assert out


@pytest.mark.asyncio
async def test_dispatch_routes_to_langgraph_when_flag_true(monkeypatch):
    """flag=True → 走 LangGraph react_graph 路径。"""
    from app.domain.agent import dispatch as dispatch_module
    monkeypatch.setattr(get_settings(), "langgraph_enabled", True, raising=False)

    called = {"path": None}

    async def fake_react_turn(session_id, message):
        called["path"] = "react_loop"
        yield b""

    async def fake_langgraph_turn(session_id, message):
        called["path"] = "langgraph"
        yield b'{"event":"turn_complete"}\n'

    monkeypatch.setattr(dispatch_module, "_run_react_loop_turn", fake_react_turn)
    monkeypatch.setattr(dispatch_module, "_run_langgraph_turn", fake_langgraph_turn)

    out = []
    async for sse in run_agent_turn(session_id="t1", message="hi"):
        out.append(sse)
    assert called["path"] == "langgraph"
