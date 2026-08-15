"""混合检索测试(RRF 融合 + 降级)。"""
from unittest.mock import patch, AsyncMock, MagicMock

import pytest

from app.services.hybrid_search import HybridSearch, rrf_fusion


class TestRRFFusion:
    def test_empty_inputs_return_empty(self) -> None:
        """空输入应返回空列表。"""
        assert rrf_fusion([], [], top_k=5) == []

    def test_only_vector_results(self) -> None:
        """只有向量结果时,chunk 来源应标记为 ['vector']。"""
        vector = [
            {"id": "c1", "content": "x", "metadata": {}},
            {"id": "c2", "content": "y", "metadata": {}},
        ]
        fused = rrf_fusion(vector, [], top_k=5, k=60)
        assert len(fused) == 2
        # c1 排第一(rank 1)
        assert fused[0]["id"] == "c1"
        for c in fused:
            assert c["_sources"] == ["vector"]

    def test_only_keyword_results(self) -> None:
        """只有关键词结果时,chunk 来源应标记为 ['keyword']。"""
        keyword = [
            {"id": "c1", "content": "x", "metadata": {}},
        ]
        fused = rrf_fusion([], keyword, top_k=5, k=60)
        assert len(fused) == 1
        assert fused[0]["_sources"] == ["keyword"]

    def test_chunk_in_both_lists_scores_higher(self) -> None:
        """出现在两路结果中的 chunk 分数应更高(双路加分)。"""
        vector = [
            {"id": "c1", "content": "x", "metadata": {}},
            {"id": "c2", "content": "y", "metadata": {}},
        ]
        keyword = [
            {"id": "c2", "content": "y", "metadata": {}},  # c2 也在 keyword 中
            {"id": "c3", "content": "z", "metadata": {}},
        ]
        fused = rrf_fusion(vector, keyword, top_k=5, k=60)
        # c2 双路命中 → RRF 分数最高
        assert fused[0]["id"] == "c2"
        assert set(fused[0]["_sources"]) == {"vector", "keyword"}

    def test_top_k_limits_results(self) -> None:
        """结果应被 top_k 限制。"""
        vector = [{"id": f"c{i}", "content": "x", "metadata": {}} for i in range(10)]
        keyword = [{"id": f"k{i}", "content": "y", "metadata": {}} for i in range(10)]
        fused = rrf_fusion(vector, keyword, top_k=3, k=60)
        assert len(fused) == 3

    def test_rrf_score_present(self) -> None:
        """每个融合结果应带 _rrf_score 字段(> 0)。"""
        vector = [{"id": "c1", "content": "x", "metadata": {}}]
        fused = rrf_fusion(vector, [], top_k=5, k=60)
        assert "_rrf_score" in fused[0]
        assert fused[0]["_rrf_score"] > 0


class TestHybridSearchFallback:
    @pytest.mark.asyncio
    async def test_falls_back_to_keyword_when_vector_fails(self) -> None:
        """向量搜索抛异常时,应降级到纯关键词,不能崩。"""
        with patch("app.services.hybrid_search.VectorIndex") as MockIndex:
            MockIndex.return_value.query.side_effect = Exception("ChromaDB down")

            with patch("app.services.hybrid_search.KnowledgeRepository") as MockRepo:
                mock_chunk = type("Chunk", (), {
                    "id": "c1", "doc_id": "d1", "kb_id": "kb1",
                    "chunk_index": 0, "content": "test content"
                })()
                MockRepo.return_value.search_chunks_by_keyword = AsyncMock(
                    return_value=[mock_chunk]
                )
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
        """两路都成功时,应返回 RRF 融合结果(双路命中排前)。"""
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

        # c2 双路命中,排第一
        assert results[0]["id"] == "c2"
        # c1 也在结果中(只在向量)
        ids = {r["id"] for r in results}
        assert "c1" in ids