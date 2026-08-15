"""验证 Langfuse 接入（P1#18 / Task 19）。

行为契约：
- init_langfuse() 在缺 LANGFUSE_PUBLIC_KEY / LANGFUSE_SECRET_KEY 时静默 no-op
- 两者都齐全时构造 Langfuse 客户端(供 LLM 调用 instrumentation 使用)
- 提供 get_langfuse() 单例获取客户端,未初始化返回 None
"""
from __future__ import annotations

from unittest.mock import patch

import pytest


def test_init_langfuse_no_public_key_does_not_crash() -> None:
    """缺 LANGFUSE_PUBLIC_KEY 时 init_langfuse 应静默 no-op。"""
    from app.core.langfuse_init import init_langfuse, get_langfuse

    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.delenv("LANGFUSE_PUBLIC_KEY", raising=False)
    monkeypatch.delenv("LANGFUSE_SECRET_KEY", raising=False)
    try:
        result = init_langfuse()
        assert result is False
        assert get_langfuse() is None
    finally:
        monkeypatch.undo()


def test_init_langfuse_no_secret_key_does_not_crash() -> None:
    """缺 LANGFUSE_SECRET_KEY 时静默 no-op。"""
    from app.core.langfuse_init import init_langfuse

    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setenv("LANGFUSE_PUBLIC_KEY", "pk-test-123")
    monkeypatch.delenv("LANGFUSE_SECRET_KEY", raising=False)
    try:
        result = init_langfuse()
        assert result is False
    finally:
        monkeypatch.undo()


def test_init_langfuse_with_both_keys_returns_client() -> None:
    """两个 key 都齐全时应构造 Langfuse 客户端并缓存。"""
    from app.core.langfuse_init import init_langfuse, get_langfuse

    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setenv("LANGFUSE_PUBLIC_KEY", "pk-test-123")
    monkeypatch.setenv("LANGFUSE_SECRET_KEY", "sk-test-456")
    monkeypatch.setenv("LANGFUSE_HOST", "https://cloud.langfuse.com")
    try:
        with patch("app.core.langfuse_init.Langfuse") as MockLangfuse:
            result = init_langfuse()
            assert result is True
            MockLangfuse.assert_called_once()
            # get_langfuse 应返回缓存的客户端
            client = get_langfuse()
            assert client is not None
    finally:
        monkeypatch.undo()


def test_init_langfuse_idempotent() -> None:
    """重复 init_langfuse 不应重复构造客户端。"""
    from app.core.langfuse_init import init_langfuse, reset_langfuse_for_test
    reset_langfuse_for_test()

    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setenv("LANGFUSE_PUBLIC_KEY", "pk-test-123")
    monkeypatch.setenv("LANGFUSE_SECRET_KEY", "sk-test-456")
    try:
        with patch("app.core.langfuse_init.Langfuse") as MockLangfuse:
            init_langfuse()
            init_langfuse()
            init_langfuse()
            # 只构造一次
            MockLangfuse.assert_called_once()
    finally:
        monkeypatch.undo()
        reset_langfuse_for_test()


def test_get_langfuse_returns_none_when_not_initialized() -> None:
    """未 init 时 get_langfuse 返回 None（供 LLM client 优雅退化）。"""
    from app.core.langfuse_init import get_langfuse, reset_langfuse_for_test
    reset_langfuse_for_test()
    assert get_langfuse() is None