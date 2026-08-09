"""T8 验证:dispatch 单一 LangGraph 路径。

- dispatch.run_agent_turn 不再有 langgraph_enabled / _run_react_loop_turn 分支
- config.langgraph_enabled 字段被删除
- agent_chat HITL resume 入口走 resume.resume_from_checkpoint(非 react_loop)
"""
from __future__ import annotations

import inspect

from app.domain.agent import dispatch


def test_no_react_loop_branch_in_dispatch():
    """dispatch.py run_agent_turn 不再有 react_loop 分支(单 LangGraph / orchestrator 路径)。

    _run_react_loop_turn 可作为 T9 parity shim 存在(供 evals/runner.py --compare),
    但 run_agent_turn 主入口已不再走 react_loop 路径。
    """
    src = inspect.getsource(dispatch)
    assert "langgraph_enabled" not in src
    # 校验 _run_react_loop_turn 不出现在 run_agent_turn 函数体内(分支调用)
    run_agent_turn_src = inspect.getsource(dispatch.run_agent_turn)
    assert "_run_react_loop_turn" not in run_agent_turn_src
    # 仍保留 _run_langgraph_turn(单路径入口)
    assert "_run_langgraph_turn" in src or "LangGraph" in src


def test_dispatch_run_agent_turn_signature_preserved():
    """run_agent_turn 签名:前两位固定(session_id, message),device_id 为可选透传。

    agent_chat API 传 device_id(L2 偏好关联);签名向后兼容(位置参数不变)。
    """
    sig = inspect.signature(dispatch.run_agent_turn)
    params = list(sig.parameters.keys())
    assert params[:2] == ["session_id", "message"]
    assert sig.parameters["device_id"].default is None


def test_config_no_langgraph_enabled_field():
    """Settings 不再有 langgraph_enabled 字段(plan:删 langgraph_enabled flag)。"""
    from app.core.config import get_settings

    settings = get_settings()
    # hasattr 检查;如果已删,hasattr 返回 False
    assert not hasattr(settings, "langgraph_enabled")


def test_agent_chat_uses_resume_module():
    """agent_chat.py HITL resume 入口引用 langgraph_nodes.resume,不引用 react_loop。"""
    import os
    import pathlib

    agent_chat_path = pathlib.Path(
        os.path.dirname(__file__)
    ).parents[1] / "app" / "api" / "agent_chat.py"
    src = agent_chat_path.read_text(encoding="utf-8")

    # HITL resume 路径走 resume.resume_from_checkpoint
    assert "resume.resume_from_checkpoint" in src or "resume_from_checkpoint" in src
    # 不再走 react_loop.run_agent_turn_from_checkpoint
    assert "react_loop.run_agent_turn_from_checkpoint" not in src
