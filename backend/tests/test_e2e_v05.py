"""E2E test for v0.5 hybrid search: verifies semantic + keyword blending works."""
from unittest.mock import patch
import numpy as np

import pytest

from app.services.hybrid_search import rrf_fusion


class TestHybridSearchEndToEnd:
    def test_semantic_match_beats_keyword_only(self) -> None:
        """Scenario: user searches for 'long battery' but doc has '5000mAh capacity'.
        Vector search finds the doc; keyword search misses it.
        Hybrid should find the doc (via vector) where keyword-only would miss.
        """
        # doc1: "phone has 5000mAh capacity, charges fast" (vector match for "long battery")
        # doc2: "phone has long battery, lasts all day" (keyword match for "long battery")
        vector_results = [
            {"id": "doc1", "content": "5000mAh capacity, charges fast", "metadata": {}, "distance": 0.15},
        ]
        keyword_results = [
            {"id": "doc2", "content": "long battery, lasts all day", "metadata": {}},
        ]

        fused = rrf_fusion(vector_results, keyword_results, top_k=5)
        assert len(fused) == 2
        ids = [c["id"] for c in fused]
        assert "doc1" in ids
        assert "doc2" in ids
        # Both should be present; vector-only doc1 and keyword-only doc2

    def test_chunk_in_both_lists_dominates(self) -> None:
        """A chunk matching both lists should be ranked highest."""
        vector_results = [
            {"id": "shared", "content": "x", "metadata": {}, "distance": 0.1},
            {"id": "vec_only", "content": "y", "metadata": {}, "distance": 0.2},
        ]
        keyword_results = [
            {"id": "shared", "content": "x", "metadata": {}},
            {"id": "kw_only", "content": "z", "metadata": {}},
        ]
        fused = rrf_fusion(vector_results, keyword_results, top_k=3)
        # shared score: 1/61 + 1/61 = 0.0328 (highest)
        # vec_only: 1/61 = 0.0164
        # kw_only: 1/61 = 0.0164
        assert fused[0]["id"] == "shared"
        # vec_only and kw_only tied for second; just verify shared is first
        assert "vec_only" in {c["id"] for c in fused}
        assert "kw_only" in {c["id"] for c in fused}

    def test_rrf_score_higher_for_dual_source(self) -> None:
        """A dual-source chunk should have higher RRF score than single-source."""
        vector_results = [
            {"id": "shared", "content": "x", "metadata": {}, "distance": 0.1},
            {"id": "vec_only", "content": "y", "metadata": {}, "distance": 0.2},
        ]
        keyword_results = [
            {"id": "shared", "content": "x", "metadata": {}},
            {"id": "kw_only", "content": "z", "metadata": {}},
        ]
        fused = rrf_fusion(vector_results, keyword_results, top_k=3)
        scores = {c["id"]: c["_rrf_score"] for c in fused}
        assert scores["shared"] > scores["vec_only"]
        assert scores["shared"] > scores["kw_only"]

    def test_k_constant_affects_score_but_not_ordering(self) -> None:
        """Different k values should give different absolute scores but same ordering."""
        vector = [{"id": "c1", "content": "x", "metadata": {}}]
        keyword = [{"id": "c1", "content": "x", "metadata": {}}]
        fused_k60 = rrf_fusion(vector, keyword, top_k=5, k=60)
        fused_k10 = rrf_fusion(vector, keyword, top_k=5, k=10)
        # Same ordering
        assert fused_k60[0]["id"] == fused_k10[0]["id"] == "c1"
        # Different absolute scores (k10 gives higher)
        assert fused_k10[0]["_rrf_score"] > fused_k60[0]["_rrf_score"]