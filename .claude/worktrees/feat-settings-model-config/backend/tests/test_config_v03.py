"""Tests for v0.3 settings additions."""
from app.core.config import Settings


def test_v03_settings_have_defaults() -> None:
    s = Settings()
    assert s.publish_timeout_s == 30
    assert s.monitor_change_threshold_default == 0.15
    assert s.smtp_port == 587
    assert s.smtp_use_tls is True
