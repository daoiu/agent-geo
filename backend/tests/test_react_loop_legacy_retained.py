"""Task 14 — 确保 langgraph_enabled=False 路径与 v0.7 react_loop 行为等价。

通过 monkeypatch _run_react_loop_turn / _run_langgraph_turn 隔离真实 IO。
"""
import pytest

from app.core.config import get_settings
from app.domain.agent.dispatch import run_agent_turn


@pytest.mark.asyncio
async def test_langgraph_disabled_uses_react_loop_path(monkeypatch):
    """flag=False → dispatch 调 _run_react_loop_turn,产 turn_complete 字节。"""
    from app.domain.agent import dispatch as dispatch_module
    monkeypatch.setattr(get_settings(), "langgraph_enabled", False, raising=False)

    async def fake_react(session_id, message):
        yield b'{"event":"assistant_message","content":"hi"}\n'
        yield b'{"event":"turn_complete"}\n'

    async def fake_lang(session_id, message):
        yield b""

    monkeypatch.setattr(dispatch_module, "_run_react_loop_turn", fake_react)
    monkeypatch.setattr(dispatch_module, "_run_langgraph_turn", fake_lang)

    out = []
    async for sse in run_agent_turn(session_id="t", message="hi"):
        out.append(sse)

    assert b"turn_complete" in b"".join(out)


@pytest.mark.asyncio
async def test_langgraph_enabled_does_not_break_dispatch(monkeypatch):
    """flag=True 时也必须可调,且进入 _run_langgraph_turn 路径。"""
    from app.domain.agent import dispatch as dispatch_module
    monkeypatch.setattr(get_settings(), "langgraph_enabled", True, raising=False)

    seen = {"path": None}

    async def fake_react(session_id, message):
        seen["path"] = "react"
        yield b""

    async def fake_lang(session_id, message):
        seen["path"] = "lang"
        yield b'{"event":"turn_complete"}\n'

    monkeypatch.setattr(dispatch_module, "_run_react_loop_turn", fake_react)
    monkeypatch.setattr(dispatch_module, "_run_langgraph_turn", fake_lang)

    out = []
    async for sse in run_agent_turn(session_id="t", message="hi"):
        out.append(sse)
        if len(out) > 10:
            break

    assert seen["path"] == "lang"
