"""Tests for the health check endpoint."""
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_endpoint_returns_ok() -> None:
    """GET /health returns 200 and {'status': 'ok'}."""
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_health_endpoint_does_not_require_auth() -> None:
    """Health check has no auth requirements."""
    response = client.get("/health", headers={})
    assert response.status_code == 200
