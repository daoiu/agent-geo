"""验证 Sentry 接入（P1#17 / Task 18）。

行为契约：
- init_sentry(dsn=None) 在 DSN 为 None/空时不初始化 Sentry（容错）
- init_sentry(dsn='xxx') 在 DSN 非空时调 sentry_sdk.init
- SENTRY_DSN env 缺失时整个应用不崩（per handoff §应急：env 占位）
- 配置项：traces_sample_rate / environment / release
"""
from __future__ import annotations

import os
from unittest.mock import patch

import pytest


def test_init_sentry_with_none_dsn_does_not_crash() -> None:
    """dsn=None 时 init_sentry 应静默 no-op,不打 sentry_sdk.init。"""
    from app.core.sentry_init import init_sentry

    with patch("app.core.sentry_init.sentry_sdk") as mock_sdk:
        init_sentry(dsn=None, environment="test", release="test@1.0.0")
        mock_sdk.init.assert_not_called()


def test_init_sentry_with_empty_dsn_does_not_crash() -> None:
    """dsn='' 时 init_sentry 应静默 no-op。"""
    from app.core.sentry_init import init_sentry

    with patch("app.core.sentry_init.sentry_sdk") as mock_sdk:
        init_sentry(dsn="", environment="test", release="test@1.0.0")
        mock_sdk.init.assert_not_called()


def test_init_sentry_with_valid_dsn_calls_init() -> None:
    """dsn 非空时 init_sentry 应调 sentry_sdk.init 并传入正确参数。"""
    from app.core.sentry_init import init_sentry

    with patch("app.core.sentry_init.sentry_sdk") as mock_sdk:
        init_sentry(
            dsn="https://abc123@sentry.io/123",
            environment="production",
            release="geo2@v0.6",
            traces_sample_rate=0.1,
        )
        mock_sdk.init.assert_called_once()
        call_kwargs = mock_sdk.init.call_args.kwargs
        assert call_kwargs["dsn"] == "https://abc123@sentry.io/123"
        assert call_kwargs["environment"] == "production"
        assert call_kwargs["release"] == "geo2@v0.6"
        assert call_kwargs["traces_sample_rate"] == 0.1


def test_init_sentry_default_traces_sample_rate_is_low() -> None:
    """默认 traces_sample_rate 应较低（避免性能影响）。"""
    from app.core.sentry_init import init_sentry

    with patch("app.core.sentry_init.sentry_sdk") as mock_sdk:
        init_sentry(dsn="https://test@sentry.io/1")
        call_kwargs = mock_sdk.init.call_args.kwargs
        assert call_kwargs["traces_sample_rate"] <= 0.2, (
            f"默认采样率应 <= 0.2,实际 {call_kwargs['traces_sample_rate']}"
        )


def test_init_sentry_from_settings() -> None:
    """init_sentry_from_settings 应从 Settings 读 SENTRY_DSN env 并初始化。"""
    from app.core.sentry_init import init_sentry_from_settings

    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setenv("SENTRY_DSN", "https://env@sentry.io/999")
    try:
        with patch("app.core.sentry_init.sentry_sdk") as mock_sdk:
            init_sentry_from_settings()
            mock_sdk.init.assert_called_once()
            assert mock_sdk.init.call_args.kwargs["dsn"] == "https://env@sentry.io/999"
    finally:
        monkeypatch.undo()


def test_init_sentry_from_settings_no_env_does_not_crash() -> None:
    """SENTRY_DSN env 缺失时 init_sentry_from_settings 应静默。"""
    from app.core.sentry_init import init_sentry_from_settings

    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.delenv("SENTRY_DSN", raising=False)
    try:
        with patch("app.core.sentry_init.sentry_sdk") as mock_sdk:
            init_sentry_from_settings()  # 不应抛
            mock_sdk.init.assert_not_called()
    finally:
        monkeypatch.undo()