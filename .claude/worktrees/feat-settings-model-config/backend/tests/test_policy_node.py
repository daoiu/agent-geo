"""Task 10 PolicyNode — transient / programming 区分 + retry。

_placeholder 异常类在 conftest / 测试体定义,不污染 app 主代码。
"""
import pytest
from tenacity import RetryError

from app.domain.agent.langgraph_nodes.policy import policy_llm_call, policy_tool_call


# 简易测试异常
class _TransientLLMError(Exception):
    """模拟 _LLM_TRANSIENT_EXCEPTIONS 包含的 transient 异常。"""


class _ProgrammingError(Exception):
    """模拟编程错误(不在 transient tuple 内)。"""


@pytest.fixture
def patch_llm(monkeypatch):
    """monkeypatch._call_llm 为 fake_llm,monkeypatch._call_tool 为 fake_tool."""
    pass  # individual tests below use monkeypatch directly


def test_policy_llm_call_retries_on_transient(monkeypatch):
    from app.domain.agent.langgraph_nodes import policy as policy_module

    # 把 _LLM_TRANSIENT_EXCEPTIONS 替换为只包含 _TransientLLMError 的 tuple
    monkeypatch.setattr(policy_module, "_LLM_TRANSIENT_EXCEPTIONS", (_TransientLLMError,))

    calls = {"n": 0}

    def fake_call_llm(state, llm_client):
        calls["n"] += 1
        if calls["n"] < 3:
            raise _TransientLLMError("rate limit")
        return {"messages": []}

    monkeypatch.setattr(policy_module, "_call_llm", fake_call_llm)

    # 设置 max_retries >= 3
    from app.core.config import Settings
    monkeypatch.setattr(Settings, "max_retries", 5, raising=False)

    out = policy_llm_call({"messages": [], "session_id": "s1"}, runtime=None, llm_client=None)
    assert calls["n"] == 3
    assert out == {"messages": []}


def test_policy_llm_call_does_not_retry_on_programming(monkeypatch):
    from app.domain.agent.langgraph_nodes import policy as policy_module

    calls = {"n": 0}

    def fake_call_llm(state, llm_client):
        calls["n"] += 1
        raise _ProgrammingError("schema drift")

    monkeypatch.setattr(policy_module, "_call_llm", fake_call_llm)

    with pytest.raises(_ProgrammingError):
        policy_llm_call({"messages": [], "session_id": "s1"}, runtime=None, llm_client=None)
    assert calls["n"] == 1


def test_policy_tool_call_does_not_retry_on_programming(monkeypatch):
    from app.domain.agent.langgraph_nodes import policy as policy_module

    calls = {"n": 0}

    def fake_call_tool(state, tool_executor, tool_call):
        calls["n"] += 1
        raise _ProgrammingError("bad arg")

    monkeypatch.setattr(policy_module, "_call_tool", fake_call_tool)

    with pytest.raises(_ProgrammingError):
        policy_tool_call(
            {"messages": [], "session_id": "s1"},
            runtime=None,
            tool_executor=None,
            tool_call={"name": "x"},
        )
    assert calls["n"] == 1
