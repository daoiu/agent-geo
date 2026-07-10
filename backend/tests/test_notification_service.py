"""Tests for notification service."""
from unittest.mock import patch, AsyncMock

import pytest

from app.domain.notification.notification_service import (
    notify_publish_failure,
    notify_publish_success,
)


@pytest.mark.asyncio
async def test_notify_publish_success(monkeypatch) -> None:
    mock_send = AsyncMock()
    monkeypatch.setattr("app.domain.notification.notification_service.send_email", mock_send)
    await notify_publish_success(
        title="测试文章", remote_url="https://example.com/?p=42", site_name="主站",
        recipient="user@example.com",
    )
    mock_send.assert_called_once()
    call_args = mock_send.call_args
    assert "成功" in call_args.kwargs.get("subject", "") or "成功" in call_args.args[1]


@pytest.mark.asyncio
async def test_notify_publish_failure(monkeypatch) -> None:
    mock_send = AsyncMock()
    monkeypatch.setattr("app.domain.notification.notification_service.send_email", mock_send)
    await notify_publish_failure(
        title="测试文章", error="认证失败", site_name="主站",
        recipient="user@example.com",
    )
    mock_send.assert_called_once()
    call_args = mock_send.call_args
    assert "失败" in call_args.kwargs.get("subject", "") or "失败" in call_args.args[1]
