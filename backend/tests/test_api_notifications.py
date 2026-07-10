"""Integration tests for notifications API."""
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient


def test_send_test_email(client: TestClient) -> None:
    with patch("app.api.notifications.send_email", new=AsyncMock()) as mock_send:
        resp = client.post(
            "/api/notifications/test",
            json={"to": "test@example.com"},
        )
    assert resp.status_code == 200
    mock_send.assert_called_once()
    call_args = mock_send.call_args
    assert "test" in call_args.kwargs.get("subject", "").lower() or "test" in call_args.args[1].lower()


def test_send_test_email_requires_email(client: TestClient) -> None:
    resp = client.post("/api/notifications/test", json={})
    assert resp.status_code == 422
