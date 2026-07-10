"""v0.5 混合检索 E2E 测试(语义 + 关键词融合)。"""
from unittest.mock import patch
import numpy as np

import pytest

from app.services.hybrid_search import rrf_fusion


class TestHybridSearchEndToEnd:
    def test_semantic_match_beats_keyword_only(self) -> None:
        """场景:用户搜"长续航"但文档是"5000mAh 容量"。向量能找到,关键词找不到。混合应至少命中。"""
        # doc1: "phone has 5000mAh capacity, charges fast" (向量命中 "长续航")
        # doc2: "phone has long battery, lasts all day" (关键词命中 "long battery")
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

    def test_chunk_in_both_lists_dominates(self) -> None:
        """双路命中的 chunk 应排第一(分数 = 1/61 + 1/61 = 0.0328)。"""
        vector_results = [
            {"id": "shared", "content": "x", "metadata": {}, "distance": 0.1},
            {"id": "vec_only", "content": "y", "metadata": {}, "distance": 0.2},
        ]
        keyword_results = [
            {"id": "shared", "content": "x", "metadata": {}},
            {"id": "kw_only", "content": "z", "metadata": {}},
        ]
        fused = rrf_fusion(vector_results, keyword_results, top_k=3)
        assert fused[0]["id"] == "shared"
        assert "vec_only" in {c["id"] for c in fused}
        assert "kw_only" in {c["id"] for c in fused}

    def test_rrf_score_higher_for_dual_source(self) -> None:
        """双路命中 chunk 的 RRF 分数应严格高于单路命中。"""
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
        """不同 k 值给不同绝对分数但不影响排序。"""
        vector = [{"id": "c1", "content": "x", "metadata": {}}]
        keyword = [{"id": "c1", "content": "x", "metadata": {}}]
        fused_k60 = rrf_fusion(vector, keyword, top_k=5, k=60)
        fused_k10 = rrf_fusion(vector, keyword, top_k=5, k=10)
        # 同序
        assert fused_k60[0]["id"] == fused_k10[0]["id"] == "c1"
        # 不同绝对分数(k10 更高)
        assert fused_k10[0]["_rrf_score"] > fused_k60[0]["_rrf_score"]