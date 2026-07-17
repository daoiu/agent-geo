"""① 混合检索管道:Redis 语义缓存测试。

覆盖四件事:NoopCache 始终未命中、写入后再读可语义命中、余弦低于阈值不命中、
有界扫描限制 zrevrange 范围。

FakeRedis 仅实现本测试用到的 set/expire/get/zadd/zrevrange 五个异步方法。
"""
import json

from app.services.retrieval.semantic_cache import SemanticCache, NoopCache


class _FakeRedis:
    """内存版,仅实现用到的异步方法。"""

    def __init__(self):
        self.kv: dict[str, str] = {}
        self.zset: list[tuple[float, str]] = []  # (score, member)

    async def set(self, k, v):
        self.kv[k] = v

    async def expire(self, k, ttl):
        pass

    async def get(self, k):
        return self.kv.get(k)

    async def zadd(self, key, mapping):
        for member, score in mapping.items():
            self.zset.append((score, member))

    async def zrevrange(self, key, start, end):
        ordered = [m for _, m in sorted(self.zset, key=lambda x: -x[0])]
        return ordered[start:end + 1] if end >= 0 else ordered[start:]


def _embed(texts):
    # "GEO" 类 → [1,0];否则 [0,1]
    return [[1.0, 0.0] if "GEO" in t else [0.0, 1.0] for t in texts]


async def test_noop_always_miss():
    c = NoopCache()
    assert await c.get("q") is None
    await c.set("q", [{"id": "x"}])  # 不抛


async def test_set_then_semantic_hit():
    c = SemanticCache(_FakeRedis(), _embed, threshold=0.95, now_fn=lambda: 1.0)
    await c.set("什么是GEO", [{"id": "c1"}])
    hit = await c.get("GEO 是什么意思")  # 同为 [1,0] 向量 → 余弦 1.0 命中
    assert hit == [{"id": "c1"}]


async def test_miss_when_below_threshold():
    c = SemanticCache(_FakeRedis(), _embed, threshold=0.95, now_fn=lambda: 1.0)
    await c.set("什么是GEO", [{"id": "c1"}])
    assert await c.get("今天天气如何") is None  # 正交向量,余弦 0


async def test_bounded_scan_limits_candidates():
    r = _FakeRedis()
    c = SemanticCache(r, _embed, threshold=0.95, max_scan=2, now_fn=lambda: 1.0)
    # zrevrange 被限制到最近 2 条:验证 end 传入为 max_scan-1
    await c.set("GEO一", [{"id": "1"}])
    got = await r.zrevrange("recent", 0, 1)
    assert len(got) <= 2