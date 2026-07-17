"""重排:Cross-Encoder(bge-reranker,本地)+ 恒等降级。

- IdentityReranker:无模型/降级场景,保持原序截断 top_k
- CrossEncoderReranker:加载 sentence_transformers.CrossEncoder,按模型打分排序
- get_reranker(settings):未启用或加载失败 → IdentityReranker(降级不抛)

模型走本地 ./data/models 缓存目录(避免运行时联网下载)。
"""
from __future__ import annotations

import structlog

logger = structlog.get_logger()


class IdentityReranker:
    """无模型降级:保持原序,截断 top_k。"""

    def rerank(self, query: str, candidates: list[dict], top_k: int) -> list[dict]:
        return candidates[:top_k]


class CrossEncoderReranker:
    """单例化加载 Cross-Encoder,避免每次重排重新加载权重。"""

    _model = None

    def __init__(self, model_name: str, cache_dir: str) -> None:
        from sentence_transformers import CrossEncoder
        if CrossEncoderReranker._model is None:
            # sentence-transformers 3.x 把 cache_folder 改名为 cache_folder → cache_dir 都接受
            # 优先传 cache_dir,旧版本则回退 cache_folder,避免 TypeError 触发降级
            try:
                CrossEncoderReranker._model = CrossEncoder(model_name, cache_dir=cache_dir)
            except TypeError:
                CrossEncoderReranker._model = CrossEncoder(model_name, cache_folder=cache_dir)
        self._model = CrossEncoderReranker._model

    def rerank(self, query: str, candidates: list[dict], top_k: int) -> list[dict]:
        if not candidates:
            return []
        pairs = [(query, c.get("content", "")) for c in candidates]
        scores = self._model.predict(pairs)
        ranked = sorted(
            zip(candidates, scores), key=lambda x: -float(x[1])
        )[:top_k]
        return [{**c, "_rerank_score": float(s)} for c, s in ranked]


def get_reranker(settings):
    """未启用或加载失败 → IdentityReranker(降级不抛)。"""
    if not settings.rerank_enabled:
        return IdentityReranker()
    try:
        return CrossEncoderReranker(settings.rerank_model_name, settings.models_cache_dir)
    except Exception as e:  # noqa: BLE001
        logger.warning("reranker_load_failed_fallback_identity", error=str(e))
        return IdentityReranker()