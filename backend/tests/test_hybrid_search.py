"""Tests for hybrid search (RRF fusion + fallback)."""
from unittest.mock import patch, AsyncMock, MagicMock

import pytest

from app.services.hybrid_search import HybridSearch, rrf_fusion


class TestRRFFusion:
    def test_empty_inputs_return_empty(self) -> None:
        assert rrf_fusion([], [], top_k=5) == []

    def test_only_vector_results(self) -> None:
        vector = [
            {"id": "c1", "content": "x", "metadata": {}},
            {"id": "c2", "content": "y", "metadata": {}},
        ]
        fused = rrf_fusion(vector, [], top_k=5, k=60)
        assert len(fused) == 2
        # c1 should rank first (rank 1)
        assert fused[0]["id"] == "c1"
        # Both should have vector source only
        for c in fused:
            assert c["_sources"] == ["vector"]

    def test_only_keyword_results(self) -> None:
        keyword = [
            {"id": "c1", "content": "x", "metadata": {}},
        ]
        fused = rrf_fusion([], keyword, top_k=5, k=60)
        assert len(fused) == 1
        assert fused[0]["_sources"] == ["keyword"]

    def test_chunk_in_both_lists_scores_higher(self) -> None:
        """A chunk in both lists should be summed (higher score)."""
        vector = [
            {"id": "c1", "content": "x", "metadata": {}},
            {"id": "c2", "content": "y", "metadata": {}},
        ]
        keyword = [
            {"id": "c2", "content": "y", "metadata": {}},  # c2 also in keyword
            {"id": "c3", "content": "z", "metadata": {}},
        ]
        fused = rrf_fusion(vector, keyword, top_k=5, k=60)
        # c2 appears in both → higher RRF score
        assert fused[0]["id"] == "c2"
        # c2's _sources should have both
        assert set(fused[0]["_sources"]) == {"vector", "keyword"}

    def test_top_k_limits_results(self) -> None:
        vector = [{"id": f"c{i}", "content": "x", "metadata": {}} for i in range(10)]
        keyword = [{"id": f"k{i}", "content": "y", "metadata": {}} for i in range(10)]
        fused = rrf_fusion(vector, keyword, top_k=3, k=60)
        assert len(fused) == 3

    def test_rrf_score_present(self) -> None:
        vector = [{"id": "c1", "content": "x", "metadata": {}}]
        fused = rrf_fusion(vector, [], top_k=5, k=60)
        assert "_rrf_score" in fused[0]
        assert fused[0]["_rrf_score"] > 0


class TestHybridSearchFallback:
    @pytest.mark.asyncio
    async def test_falls_back_to_keyword_when_vector_fails(self) -> None:
        """If vector search raises, hybrid should return keyword results."""
        with patch("app.services.hybrid_search.VectorIndex") as MockIndex:
            MockIndex.return_value.query.side_effect = Exception("ChromaDB down")

            # Also need to patch the keyword search via repository
            with patch("app.services.hybrid_search.KnowledgeRepository") as MockRepo:
                mock_chunk = type("Chunk", (), {
                    "id": "c1", "doc_id": "d1", "kb_id": "kb1",
                    "chunk_index": 0, "content": "test content"
                })()
                MockRepo.return_value.search_chunks_by_keyword = AsyncMock(
                    return_value=[mock_chunk]
                )
                # Need to mock the session context manager
                mock_session = MagicMock()
                mock_session.__aenter__ = AsyncMock(return_value=mock_session)
                mock_session.__aexit__ = AsyncMock(return_value=None)
                with patch("app.services.hybrid_search.get_session_factory") as mock_factory:
                    mock_factory.return_value.return_value = mock_session

                    results = await HybridSearch().search("kb1", "test query")

            assert len(results) >= 1
            assert results[0]["_sources"] == ["keyword"]


class TestHybridSearchNormalPath:
    @pytest.mark.asyncio
    async def test_returns_rrf_fused_results(self) -> None:
        """When both succeed, return RRF-fused results."""
        with patch("app.services.hybrid_search.VectorIndex") as MockIndex:
            MockIndex.return_value.query.return_value = [
                {"id": "c1", "content": "v1", "metadata": {}, "distance": 0.1},
                {"id": "c2", "content": "v2", "metadata": {}, "distance": 0.2},
            ]
            with patch("app.services.hybrid_search.KnowledgeRepository") as MockRepo:
                mock_chunk = type("Chunk", (), {
                    "id": "c2", "doc_id": "d1", "kb_id": "kb1",
                    "chunk_index": 0, "content": "k1"
                })()
                MockRepo.return_value.search_chunks_by_keyword = AsyncMock(
                    return_value=[mock_chunk]
                )
                mock_session = MagicMock()
                mock_session.__aenter__ = AsyncMock(return_value=mock_session)
                mock_session.__aexit__ = AsyncMock(return_value=None)
                with patch("app.services.hybrid_search.get_session_factory") as mock_factory:
                    mock_factory.return_value.return_value = mock_session

                    results = await HybridSearch().search("kb1", "test", top_k=5)

        # c2 should be first (in both lists)
        assert results[0]["id"] == "c2"
        # c1 should also be in results (only in vector)
        ids = {r["id"] for r in results}
        assert "c1" in ids