"""Tests for email sender."""
from unittest.mock import patch, AsyncMock

import pytest

from app.core.config import Settings
from app.domain.exceptions import NotificationError
from app.domain.notification.email_sender import send_email


@pytest.fixture
def smtp_settings() -> Settings:
    return Settings(
        smtp_host="smtp.example.com",
        smtp_port=587,
        smtp_user="user",
        smtp_password="pass",
        smtp_use_tls=True,
        smtp_from="test@example.com",
    )


@pytest.mark.asyncio
async def test_send_email_success(smtp_settings: Settings, monkeypatch) -> None:
    monkeypatch.setattr("app.domain.notification.email_sender.get_settings", lambda: smtp_settings)
    with patch("aiosmtplib.send", new=AsyncMock()) as mock_send:
        await send_email(to="user@example.com", subject="Test", body="Hello")
        mock_send.assert_called_once()


@pytest.mark.asyncio
async def test_send_email_no_smtp_config(monkeypatch) -> None:
    monkeypatch.setattr("app.domain.notification.email_sender.get_settings", lambda: Settings())
    with pytest.raises(NotificationError, match="SMTP not configured"):
        await send_email(to="x", subject="y", body="z")


@pytest.mark.asyncio
async def test_send_email_smtp_error(monkeypatch) -> None:
    s = Settings(smtp_host="smtp.example.com", smtp_port=587, smtp_user="u", smtp_password="p")
    monkeypatch.setattr("app.domain.notification.email_sender.get_settings", lambda: s)
    with patch("aiosmtplib.send", new=AsyncMock(side_effect=Exception("smtp down"))):
        with pytest.raises(NotificationError, match="smtp down"):
            await send_email(to="x", subject="y", body="z")
