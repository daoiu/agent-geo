"""Monitor Scheduler 接入 specialist 测试。"""
from __future__ import annotations

import os

# 测试不调用 LLM
os.environ.setdefault("GEO_ALLOW_MISSING_LLM_KEY", "1")

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.domain.monitor.scheduler import _build_monitor_callback


async def test_callback_uses_monitor_specialist():
    """scheduler 回调走 MonitorSpecialist.run,不走 execute_monitor_run。"""
    mock_settings = MagicMock(handoff_timeout_monitor=60)
    mock_factory = MagicMock()
    with patch("app.core.config.get_settings", return_value=mock_settings):
        with patch("app.core.db.get_session_factory", return_value=mock_factory):
            with patch("app.domain.monitor.monitor_specialist.MonitorSpecialist") as mock_spec_cls:
                mock_spec = MagicMock()
                mock_spec.run = AsyncMock(return_value=MagicMock(status="success"))
                mock_spec_cls.return_value = mock_spec

                callback = _build_monitor_callback()
                await callback("task-1")

    mock_spec.run.assert_called_once_with("task-1")
