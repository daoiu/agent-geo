import pytest
from app.core.config import Settings


def test_settings_has_langgraph_enabled_default_false():
    s = Settings()
    assert hasattr(s, "langgraph_enabled")
    assert s.langgraph_enabled is False


def test_settings_langgraph_enabled_can_be_overridden(monkeypatch):
    monkeypatch.setenv("LANGGRAPH_ENABLED", "true")
    s = Settings()
    assert s.langgraph_enabled is True
