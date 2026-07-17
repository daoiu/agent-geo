"""②b dispatch 接入测试(spec agent-orchestrator §6.2.6)。

flag 灰度：agent_orchestrator_enabled=True 走 run_orchestrated，False 沿用 ②a 单一路径。
"""
from app.domain.agent import dispatch


async def test_dispatch_routes_to_orchestrator(monkeypatch):
    monkeypatch.setattr(
        dispatch,
        "get_settings",
        lambda: type("S", (), {"agent_orchestrator_enabled": True})(),
    )

    async def _fake_orch(session_id, message, hint=None):
        yield b'{"event":"mode_switch","mode":"react"}\n'

    monkeypatch.setattr(dispatch, "run_orchestrated", _fake_orch, raising=False)

    outs = [x async for x in dispatch.run_agent_turn("s1", "q")]
    assert any(b"mode_switch" in x for x in outs)
