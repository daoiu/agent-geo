"""Handoff Settings 字段测试。"""
from __future__ import annotations

import os

# 测试不调用 LLM,允许缺少 API key
os.environ.setdefault("GEO_ALLOW_MISSING_LLM_KEY", "1")

from app.core.config import Settings


def test_handoff_settings_have_defaults():
    """4 个 handoff 字段必须有默认值(默认值见 spec §3.4)。"""
    # 清掉可能影响测试的 env 变量
    for key in (
        "HANDOFF_TIMEOUT_CONTENT_WRITER",
        "HANDOFF_TIMEOUT_MONITOR",
        "HANDOFF_MAX_RETRIES",
        "HANDOFF_IDEMPOTENCY_WINDOW_HOURS",
    ):
        os.environ.pop(key, None)
    s = Settings(_env_file=None)  # 避免读 .env
    assert s.handoff_timeout_content_writer == 300
    assert s.handoff_timeout_monitor == 60
    assert s.handoff_max_retries == 1
    assert s.handoff_idempotency_window_hours == 24


def test_handoff_settings_override_from_env(monkeypatch):
    """环境变量可覆盖默认值(env 注入测试)。"""
    monkeypatch.setenv("HANDOFF_TIMEOUT_CONTENT_WRITER", "600")
    monkeypatch.setenv("HANDOFF_IDEMPOTENCY_WINDOW_HOURS", "48")
    s = Settings(_env_file=None)
    assert s.handoff_timeout_content_writer == 600
    assert s.handoff_idempotency_window_hours == 48

