"""Tests for v0.2 settings additions."""
from app.core.config import Settings


def test_v02_settings_have_defaults() -> None:
    s = Settings()
    assert s.max_upload_size_mb == 50
    assert s.default_target_length == 1500
    assert s.chunk_min_length == 50
    assert s.chunk_max_length == 500
    assert s.retrieval_top_k == 5
    assert s.max_article_count_per_task == 20
