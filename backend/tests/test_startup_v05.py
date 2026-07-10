"""Test that reindex is called during app startup."""
from unittest.mock import patch, AsyncMock


def test_startup_runs_reindex() -> None:
    """The FastAPI lifespan should call ReindexService.reindex_all()."""
    with patch("app.services.reindex.ReindexService") as MockReindex:
        mock_instance = MockReindex.return_value
        mock_instance.reindex_all = AsyncMock(return_value={})

        with patch("app.domain.monitor.scheduler.load_all_monitor_tasks", new=AsyncMock()):
            from fastapi.testclient import TestClient
            from app.main import app
            with TestClient(app) as client:
                pass  # triggers lifespan startup

        mock_instance.reindex_all.assert_called()