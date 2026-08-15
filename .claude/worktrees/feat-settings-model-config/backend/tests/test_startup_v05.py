"""验证 FastAPI lifespan 启动时调 reindex。"""
from unittest.mock import patch, AsyncMock


def test_startup_runs_reindex() -> None:
    """FastAPI lifespan 启动时应调 ReindexService.reindex_all()(v0.5 启动时 lazy 向量化)。"""
    with patch("app.services.reindex.ReindexService") as MockReindex:
        mock_instance = MockReindex.return_value
        mock_instance.reindex_all = AsyncMock(return_value={})

        with patch("app.domain.monitor.scheduler.load_all_monitor_tasks", new=AsyncMock()):
            from fastapi.testclient import TestClient
            from app.main import app
            with TestClient(app) as client:
                pass  # 触发 lifespan startup

        mock_instance.reindex_all.assert_called()