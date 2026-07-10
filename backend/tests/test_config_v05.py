"""Tests for v0.5 settings additions."""
from app.core.config import Settings


def test_v05_settings_have_defaults() -> None:
    s = Settings()
    assert s.chroma_path == "./data/chroma"
    assert s.models_cache_dir == "./data/models"
    assert s.embedding_batch_size == 50
    assert s.hybrid_top_k_vector == 20
    assert s.hybrid_top_k_keyword == 20
    assert s.hybrid_rrf_k == 60