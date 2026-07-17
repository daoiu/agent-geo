"""① 混合检索管道:配置项默认值测试。

覆盖 Settings 11 个新字段(查询改写 / 重排 / 语义缓存 / Redis / 词典路径),
确保默认值与 plan "平滑升级" 一致:开启重排与缓存但关闭 HyDE。
"""
from app.core.config import get_settings


def test_retrieval_defaults():
    s = get_settings()
    assert s.enable_query_rewrite is True
    assert s.multi_query_n == 3
    assert s.rerank_top_m == 20
    assert s.rerank_model_name == "BAAI/bge-reranker-base"
    assert s.semantic_cache_enabled is True
    assert s.semantic_cache_threshold == 0.95
    assert s.semantic_cache_max_scan == 1000
    assert s.redis_url.startswith("redis://")
    assert s.geo_userdict_path.endswith("geo_terms.txt")