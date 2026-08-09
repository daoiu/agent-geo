"""LangGraph 唯一路径配置测试(commit fd0592d 删除 langgraph_enabled 开关后)。

现状: dispatch 单一 LangGraph 路径,无 ``langgraph_enabled`` 开关——
开关已随 react_loop 驱动逻辑一并删除,避免双路径分歧。
"""
import pytest
from app.core.config import Settings


def test_settings_has_no_langgraph_enabled_switch():
    """LangGraph 是唯一路径,Settings 不应再有 langgraph_enabled 开关。"""
    s = Settings()
    assert not hasattr(s, "langgraph_enabled")


def test_settings_langgraph_env_is_ignored(monkeypatch):
    """历史遗留的 LANGGRAPH_ENABLED 环境变量不应再影响配置。"""
    monkeypatch.setenv("LANGGRAPH_ENABLED", "true")
    s = Settings()
    assert not hasattr(s, "langgraph_enabled")
