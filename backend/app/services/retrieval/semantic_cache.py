"""语义缓存:Redis ZSET 维护 LRU 窗口 + 有界余弦扫描。无 Redis 时 Noop。

- get:query embed → ZREVRANGE 取最近 ≤max_scan 条 → 逐条比余弦,≥阈值命中
- set:存 cache:{id}(query/embedding/results) + EXPIRE + ZADD recent(score=时间戳)

扫描量恒定上界,延迟不随缓存总量线性增长。V2 可换 RediSearch HNSW。
"""
from __future__ import annotations

import hashlib
import json
import math
import time

import structlog

logger = structlog.get_logger()
_RECENT_KEY = "geo:cache:recent"


def _cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    return dot / (na * nb) if na and nb else 0.0


class NoopCache:
    """无 Redis / 禁用场景的占位缓存,接口对齐 SemanticCache。"""

    async def get(self, query: str):
        return None

    async def set(self, query: str, results: list[dict]) -> None:
        return None


class SemanticCache:
    """Redis 后端 + LRU ZSET 有界扫描 + 余弦相似命中。"""

    def __init__(
        self,
        client,
        embed_fn,
        threshold: float = 0.95,
        ttl_s: int = 3600,
        max_scan: int = 1000,
        now_fn=time.time,
    ) -> None:
        self.client = client
        self.embed_fn = embed_fn
        self.threshold = threshold
        self.ttl_s = ttl_s
        self.max_scan = max_scan
        self.now_fn = now_fn

    async def get(self, query: str):
        try:
            qv = self.embed_fn([query])[0]
            ids = await self.client.zrevrange(_RECENT_KEY, 0, self.max_scan - 1)
            for cid in ids:
                raw = await self.client.get(cid)
                if not raw:
                    continue
                obj = json.loads(raw)
                if _cosine(qv, obj["embedding"]) >= self.threshold:
                    return obj["results"]
        except Exception as e:  # noqa: BLE001
            logger.warning("semantic_cache_get_failed", error=str(e))
        return None

    async def set(self, query: str, results: list[dict]) -> None:
        try:
            qv = self.embed_fn([query])[0]
            cid = "geo:cache:" + hashlib.sha1(query.encode("utf-8")).hexdigest()
            payload = json.dumps(
                {"query": query, "embedding": qv, "results": results},
                ensure_ascii=False,
            )
            await self.client.set(cid, payload)
            await self.client.expire(cid, self.ttl_s)
            await self.client.zadd(_RECENT_KEY, {cid: self.now_fn()})
        except Exception as e:  # noqa: BLE001
            logger.warning("semantic_cache_set_failed", error=str(e))


def get_cache(settings, embed_fn):
    """未启用 → Noop;连接失败 → Noop(降级不抛)。"""
    if not settings.semantic_cache_enabled:
        return NoopCache()
    try:
        import redis.asyncio as aioredis
        client = aioredis.from_url(settings.redis_url, decode_responses=True)
        return SemanticCache(
            client,
            embed_fn,
            threshold=settings.semantic_cache_threshold,
            ttl_s=settings.semantic_cache_ttl_s,
            max_scan=settings.semantic_cache_max_scan,
        )
    except Exception as e:  # noqa: BLE001
        logger.warning("semantic_cache_init_failed_noop", error=str(e))
        return NoopCache()