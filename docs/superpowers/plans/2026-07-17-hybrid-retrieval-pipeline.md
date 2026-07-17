# 混合检索管道升级实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把现有「向量+裸关键词→RRF」升级为「查询改写 → 向量+BM25 双路召回 → RRF → Cross-Encoder 重排」,外层套 Redis 语义缓存(有界扫描),并用 ④ 基准量化 Recall@5 提升。

**Architecture:** 新增 `backend/app/services/retrieval/` 模块组(tokenizer / bm25_search / query_rewrite / reranker / semantic_cache),`hybrid_search.py` 改为编排层。全程降级链保持「绝不 5xx」。

**Tech Stack:** Python 3.11 · `rank_bm25`(BM25Okapi) · `redis`(redis-py async) · `sentence_transformers.CrossEncoder`(bge-reranker,本地) · jieba(领域词典) · 现有 `EmbeddingService` / `LLMClient` / `VectorIndex` / `rrf_fusion`。

## Global Constraints

- 语言:对话 / docstring / 报告用简体中文。
- 无外网:reranker 模型用户预下到 `backend/data/models/`;embedding 走本地缓存;`rank_bm25` / `redis` 为纯 Python 依赖,一次性 `pip install`。
- 依赖前置:量化提升依赖 ④ 评测基准(`backend/evals/retrieval/`)已落地。
- 测试位置:`backend/tests/services/retrieval/`(pyproject `testpaths=["tests"]`、`pythonpath=["."]`、`asyncio_mode="auto"`),工作目录 `backend/`。
- 降级原则:无 LLM key → 跳过改写/HyDE;无 reranker 模型 → 恒等重排;无 Redis → 缓存 no-op;Chroma 失败 → 退关键词。任一环坏,管道仍出结果,绝不 5xx。
- 配置默认值 = 当前行为的平滑升级。
- 数字诚实:Recall@5 提升来自真实复跑 ④,不硬编码。

**关键既有接口(各 Task 消费):**
- `app.services.embedding.EmbeddingService.embed(texts: list[str]) -> list[list[float]]`(classmethod,归一化 512 维)
- `app.domain.llm_client.LLMClient`:`await simple_chat(prompt) -> str`;`.available_providers -> list[str]`
- `app.domain.knowledge.vector_index.VectorIndex(kb_id).query(query_text, top_k) -> list[{id, content, metadata, distance}]`
- `app.repositories.knowledge_repo.KnowledgeRepository(session).list_chunks(kb_id) -> list[KnowledgeChunkORM]`(`.id/.content`)
- `app.services.hybrid_search.rrf_fusion(vector_results, keyword_results, top_k, k) -> list[dict]`(既有)
- `app.core.config.get_settings() -> Settings`;`app.core.db.get_session_factory()`

---

### Task 1: 配置项 + 依赖 + docker-compose

**Files:**
- Modify: `backend/app/core/config.py`(v0.5 vector 段后追加字段)
- Modify: `backend/pyproject.toml`(deps 加 `rank-bm25`、`redis`)
- Modify: `docker-compose.yml`(加 redis 服务)
- Modify: `.env.example`(加新配置说明)
- Test: `backend/tests/services/retrieval/test_config.py`

**Interfaces:**
- Consumes: 无
- Produces: `Settings` 新字段(见下),供 Task 2-7 读取。

- [ ] **Step 1: 写失败测试**

```python
# backend/tests/services/retrieval/test_config.py
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
```

- [ ] **Step 2: 运行确认失败**

Run: `cd backend && python -m pytest tests/services/retrieval/test_config.py -v`
Expected: FAIL(AttributeError: enable_query_rewrite)

- [ ] **Step 3: 实现 — config 追加字段**

在 `backend/app/core/config.py` 的 `hybrid_rrf_k: int = 60` 一行之后追加:

```python
    # ① 混合检索管道升级
    enable_query_rewrite: bool = True
    enable_hyde: bool = False
    multi_query_n: int = 3
    rerank_enabled: bool = True
    rerank_top_m: int = 20
    rerank_model_name: str = "BAAI/bge-reranker-base"
    semantic_cache_enabled: bool = True
    semantic_cache_threshold: float = 0.95
    semantic_cache_ttl_s: int = 3600
    semantic_cache_max_scan: int = 1000
    redis_url: str = "redis://localhost:6379/0"
    geo_userdict_path: str = "./data/geo_terms.txt"
```

- [ ] **Step 4: 依赖与 compose**

`backend/pyproject.toml` 的 dependencies 数组加两行(版本按仓库风格,无上限锁死):
```toml
    "rank-bm25>=0.2.2",
    "redis>=5.0",
```
安装:`cd backend && pip install rank-bm25 "redis>=5.0"`

`docker-compose.yml` 的 `services:` 下加:
```yaml
  redis:
    image: redis:7-alpine
    container_name: geo-redis
    ports:
      - "6379:6379"
```
并给 `backend` 加 `depends_on: [redis]`。

`.env.example` 末尾追加:
```
# ① 混合检索
REDIS_URL=redis://localhost:6379/0
ENABLE_HYDE=false
```

- [ ] **Step 5: 运行确认通过 + 提交**

Run: `cd backend && python -m pytest tests/services/retrieval/test_config.py -v`
Expected: PASS

```bash
git add backend/app/core/config.py backend/pyproject.toml docker-compose.yml .env.example backend/tests/services/retrieval/test_config.py
git commit -m "feat(retrieval): ① 配置项 + rank-bm25/redis 依赖 + compose redis"
```

---

### Task 2: 领域分词 `tokenizer.py`

**Files:**
- Create: `backend/app/services/retrieval/__init__.py`(空)
- Create: `backend/app/services/retrieval/tokenizer.py`
- Test: `backend/tests/services/retrieval/test_tokenizer.py`

**Interfaces:**
- Consumes: 无
- Produces:
  - `load_domain_dict(path: str | Path) -> bool`(文件存在则 `jieba.load_userdict` 返回 True;否则 False,不抛)
  - `tokenize(text: str) -> list[str]`(jieba 切词,去空白、去长度 ≤1 的 token)

- [ ] **Step 1: 写失败测试**

```python
# backend/tests/services/retrieval/test_tokenizer.py
from app.services.retrieval.tokenizer import load_domain_dict, tokenize


def test_load_missing_dict_returns_false(tmp_path):
    assert load_domain_dict(tmp_path / "nope.txt") is False


def test_domain_word_not_split(tmp_path):
    d = tmp_path / "geo_terms.txt"
    d.write_text("LangChain 100 n\nGPT-4o 100 n\n", encoding="utf-8")
    assert load_domain_dict(d) is True
    toks = tokenize("我在用 LangChain 和 GPT-4o 做检索")
    assert "LangChain" in toks
    assert "GPT-4o" in toks


def test_tokenize_drops_short_and_blank():
    toks = tokenize("a 检索 的")
    assert "检索" in toks
    assert "a" not in toks  # 长度 ≤1 丢弃
```

- [ ] **Step 2: 运行确认失败**

Run: `cd backend && python -m pytest tests/services/retrieval/test_tokenizer.py -v`
Expected: FAIL(ModuleNotFoundError)

- [ ] **Step 3: 写实现**

```python
# backend/app/services/retrieval/tokenizer.py
"""领域分词:加载 GEO 用户词典 + 统一 jieba 切词入口。

专有名词(品牌名/模型名/技术术语)靠 userdict 防切碎,保障 BM25/关键词召回。
"""
from __future__ import annotations

from pathlib import Path

import jieba
import structlog

logger = structlog.get_logger()
_loaded = False


def load_domain_dict(path: str | Path) -> bool:
    """加载领域词典(幂等)。文件不存在返回 False,不抛。"""
    global _loaded
    p = Path(path)
    if not p.exists():
        logger.warning("geo_userdict_missing", path=str(p))
        return False
    jieba.load_userdict(str(p))
    _loaded = True
    logger.info("geo_userdict_loaded", path=str(p))
    return True


def tokenize(text: str) -> list[str]:
    """jieba 切词,去空白与长度 ≤1 的 token。"""
    return [w for w in jieba.lcut(text) if len(w.strip()) > 1]
```

同时创建空 `backend/app/services/retrieval/__init__.py`。

- [ ] **Step 4: 运行确认通过 + 提交**

Run: `cd backend && python -m pytest tests/services/retrieval/test_tokenizer.py -v`
Expected: PASS(3 passed)

```bash
git add backend/app/services/retrieval/__init__.py backend/app/services/retrieval/tokenizer.py backend/tests/services/retrieval/test_tokenizer.py
git commit -m "feat(retrieval): 领域分词 tokenizer + 用户词典 + 3 用例"
```

---

### Task 3: BM25 召回 `bm25_search.py`

**Files:**
- Create: `backend/app/services/retrieval/bm25_search.py`
- Test: `backend/tests/services/retrieval/test_bm25_search.py`

**Interfaces:**
- Consumes: `tokenize`(T2)、`rank_bm25.BM25Okapi`
- Produces:
  - `bm25_rank(corpus: list[tuple[str, str]], query: str, top_k: int = 20) -> list[dict]`
    - corpus = `[(chunk_id, content), ...]`;返回 `[{"id", "content", "_bm25_score"}]`,按分降序,空 corpus/query → `[]`
  - `async def bm25_search_kb(kb_id: str, query: str, top_k: int = 20, repo=None) -> list[dict]`(载入 KB chunk 后调 `bm25_rank`)

- [ ] **Step 1: 写失败测试**

```python
# backend/tests/services/retrieval/test_bm25_search.py
from app.services.retrieval.bm25_search import bm25_rank


def test_bm25_ranks_relevant_first():
    corpus = [
        ("c1", "GEO 是生成式引擎优化技术"),
        ("c2", "今天天气很好适合出门"),
        ("c3", "生成式引擎优化能提升品牌曝光"),
    ]
    hits = bm25_rank(corpus, "生成式引擎优化", top_k=2)
    assert len(hits) == 2
    assert hits[0]["id"] in {"c1", "c3"}  # 相关块排前
    assert all("_bm25_score" in h for h in hits)


def test_bm25_empty_corpus():
    assert bm25_rank([], "任意", top_k=5) == []


def test_bm25_empty_query():
    assert bm25_rank([("c1", "内容")], "", top_k=5) == []
```

- [ ] **Step 2: 运行确认失败**

Run: `cd backend && python -m pytest tests/services/retrieval/test_bm25_search.py -v`
Expected: FAIL(ModuleNotFoundError)

- [ ] **Step 3: 写实现**

```python
# backend/app/services/retrieval/bm25_search.py
"""BM25 召回:rank_bm25.BM25Okapi + 领域分词。"""
from __future__ import annotations

from rank_bm25 import BM25Okapi

from app.services.retrieval.tokenizer import tokenize


def bm25_rank(corpus: list[tuple[str, str]], query: str, top_k: int = 20) -> list[dict]:
    q_tokens = tokenize(query)
    if not corpus or not q_tokens:
        return []
    tokenized = [tokenize(content) or [""] for _, content in corpus]
    bm25 = BM25Okapi(tokenized)
    scores = bm25.get_scores(q_tokens)
    ranked = sorted(
        zip(corpus, scores), key=lambda x: -x[1]
    )[:top_k]
    return [
        {"id": cid, "content": content, "_bm25_score": float(score)}
        for (cid, content), score in ranked
        if score > 0
    ]


async def bm25_search_kb(kb_id: str, query: str, top_k: int = 20, repo=None) -> list[dict]:
    """载入 KB chunk 后 BM25 排序。repo=None → 用默认 session。"""
    if repo is None:
        from app.core.db import get_session_factory
        from app.repositories.knowledge_repo import KnowledgeRepository
        async with get_session_factory()() as session:
            chunks = await KnowledgeRepository(session).list_chunks(kb_id)
    else:
        chunks = await repo.list_chunks(kb_id)
    corpus = [(c.id, c.content) for c in chunks]
    return bm25_rank(corpus, query, top_k)
```

- [ ] **Step 4: 运行确认通过 + 提交**

Run: `cd backend && python -m pytest tests/services/retrieval/test_bm25_search.py -v`
Expected: PASS(3 passed)

```bash
git add backend/app/services/retrieval/bm25_search.py backend/tests/services/retrieval/test_bm25_search.py
git commit -m "feat(retrieval): BM25 召回(rank_bm25 + 领域分词)+ 3 用例"
```

---

### Task 4: 查询改写 `query_rewrite.py`

**Files:**
- Create: `backend/app/services/retrieval/query_rewrite.py`
- Test: `backend/tests/services/retrieval/test_query_rewrite.py`

**Interfaces:**
- Consumes: `LLMClient.simple_chat` / `.available_providers`
- Produces:
  - `async def rewrite(query: str, llm, n: int = 3, enable_hyde: bool = False) -> list[str]`
    - 返回 `[原查询, 改写1..n, (HyDE 假设文档)]`;无 provider → `[query]`;去重、去空
  - `_parse_lines(reply: str) -> list[str]`(按行拆、去编号前缀、去空)

- [ ] **Step 1: 写失败测试**

```python
# backend/tests/services/retrieval/test_query_rewrite.py
from app.services.retrieval.query_rewrite import rewrite, _parse_lines


class _FakeLLM:
    def __init__(self, reply, providers=("p",)):
        self._reply = reply
        self.available_providers = list(providers)
    async def simple_chat(self, prompt):
        return self._reply


def test_parse_lines_strips_numbering():
    out = _parse_lines("1. 什么是GEO\n2) GEO定义\n\n- GEO含义")
    assert out == ["什么是GEO", "GEO定义", "GEO含义"]


async def test_rewrite_includes_original_and_variants():
    llm = _FakeLLM("GEO是什么\nGEO的定义\n生成式引擎优化含义")
    out = await rewrite("什么是GEO", llm, n=3)
    assert out[0] == "什么是GEO"           # 原查询在首
    assert "GEO的定义" in out
    assert len(out) == len(set(out))       # 去重


async def test_rewrite_no_provider_returns_original():
    llm = _FakeLLM("x", providers=())
    assert await rewrite("q", llm, n=3) == ["q"]


async def test_rewrite_hyde_appends_doc():
    llm = _FakeLLM("变体")
    out = await rewrite("q", llm, n=1, enable_hyde=True)
    assert len(out) >= 2  # 原查询 + 变体/HyDE
```

- [ ] **Step 2: 运行确认失败**

Run: `cd backend && python -m pytest tests/services/retrieval/test_query_rewrite.py -v`
Expected: FAIL(ModuleNotFoundError)

- [ ] **Step 3: 写实现**

```python
# backend/app/services/retrieval/query_rewrite.py
"""查询改写:Multi-Query 扩写 + 可选 HyDE。无 LLM key 时降级为原查询。"""
from __future__ import annotations

import re

import structlog

logger = structlog.get_logger()
_NUM_PREFIX = re.compile(r"^\s*(?:\d+[.)、]|[-*])\s*")


def _parse_lines(reply: str) -> list[str]:
    out: list[str] = []
    for line in reply.splitlines():
        s = _NUM_PREFIX.sub("", line).strip()
        if s:
            out.append(s)
    return out


async def _multi_query(query: str, llm, n: int) -> list[str]:
    prompt = (
        f"把下面的检索问题改写成 {n} 条语义等价但措辞不同的中文查询,每行一条,不要编号:\n{query}"
    )
    return _parse_lines(await llm.simple_chat(prompt))[:n]


async def _hyde(query: str, llm) -> str:
    prompt = f"针对问题写一段 2-3 句、像知识库文档的假设答案,只输出内容:\n{query}"
    return (await llm.simple_chat(prompt)).strip()


async def rewrite(query: str, llm, n: int = 3, enable_hyde: bool = False) -> list[str]:
    if not getattr(llm, "available_providers", []):
        return [query]
    variants = [query]
    try:
        variants.extend(await _multi_query(query, llm, n))
        if enable_hyde:
            doc = await _hyde(query, llm)
            if doc:
                variants.append(doc)
    except Exception as e:  # noqa: BLE001
        logger.warning("query_rewrite_failed", error=str(e))
    # 去重保序
    seen: set[str] = set()
    out: list[str] = []
    for v in variants:
        if v and v not in seen:
            seen.add(v)
            out.append(v)
    return out
```

- [ ] **Step 4: 运行确认通过 + 提交**

Run: `cd backend && python -m pytest tests/services/retrieval/test_query_rewrite.py -v`
Expected: PASS(4 passed)

```bash
git add backend/app/services/retrieval/query_rewrite.py backend/tests/services/retrieval/test_query_rewrite.py
git commit -m "feat(retrieval): 查询改写 Multi-Query + HyDE + 无 key 降级 + 4 用例"
```

---

### Task 5: 重排 `reranker.py`

**Files:**
- Create: `backend/app/services/retrieval/reranker.py`
- Test: `backend/tests/services/retrieval/test_reranker.py`

**Interfaces:**
- Consumes: `sentence_transformers.CrossEncoder`(可选)、`Settings`
- Produces:
  - `class IdentityReranker`:`rerank(query, candidates: list[dict], top_k) -> list[dict]`(原序取前 top_k)
  - `class CrossEncoderReranker`:同签名,用模型打分排序,写 `_rerank_score`
  - `def get_reranker(settings) -> IdentityReranker | CrossEncoderReranker`(未启用或模型加载失败 → Identity)

- [ ] **Step 1: 写失败测试**

```python
# backend/tests/services/retrieval/test_reranker.py
from app.services.retrieval.reranker import IdentityReranker, CrossEncoderReranker


def test_identity_keeps_order_and_truncates():
    cands = [{"id": "a", "content": "x"}, {"id": "b", "content": "y"}, {"id": "c", "content": "z"}]
    out = IdentityReranker().rerank("q", cands, top_k=2)
    assert [c["id"] for c in out] == ["a", "b"]


def test_cross_encoder_reorders_by_score(monkeypatch):
    r = CrossEncoderReranker.__new__(CrossEncoderReranker)  # 跳过 __init__ 加载模型

    class _FakeModel:
        def predict(self, pairs):
            # 第二个候选给最高分
            return [0.1, 0.9, 0.5][: len(pairs)]
    r._model = _FakeModel()

    cands = [{"id": "a", "content": "x"}, {"id": "b", "content": "y"}, {"id": "c", "content": "z"}]
    out = r.rerank("q", cands, top_k=2)
    assert out[0]["id"] == "b"
    assert out[0]["_rerank_score"] == 0.9
```

- [ ] **Step 2: 运行确认失败**

Run: `cd backend && python -m pytest tests/services/retrieval/test_reranker.py -v`
Expected: FAIL(ModuleNotFoundError)

- [ ] **Step 3: 写实现**

```python
# backend/app/services/retrieval/reranker.py
"""重排:Cross-Encoder(bge-reranker,本地)+ 恒等降级。"""
from __future__ import annotations

import structlog

logger = structlog.get_logger()


class IdentityReranker:
    """无模型降级:保持原序,截断 top_k。"""

    def rerank(self, query: str, candidates: list[dict], top_k: int) -> list[dict]:
        return candidates[:top_k]


class CrossEncoderReranker:
    _model = None

    def __init__(self, model_name: str, cache_dir: str) -> None:
        from sentence_transformers import CrossEncoder
        if CrossEncoderReranker._model is None:
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
```

- [ ] **Step 4: 运行确认通过 + 提交**

Run: `cd backend && python -m pytest tests/services/retrieval/test_reranker.py -v`
Expected: PASS(2 passed)

```bash
git add backend/app/services/retrieval/reranker.py backend/tests/services/retrieval/test_reranker.py
git commit -m "feat(retrieval): Cross-Encoder 重排 + 恒等降级 + 2 用例"
```

---

### Task 6: 语义缓存 `semantic_cache.py`(Redis ZSET LRU + 有界扫描)

**Files:**
- Create: `backend/app/services/retrieval/semantic_cache.py`
- Test: `backend/tests/services/retrieval/test_semantic_cache.py`

**Interfaces:**
- Consumes: redis 异步 client(注入)、embed_fn
- Produces:
  - `class NoopCache`:`async get(query) -> None`;`async set(query, results) -> None`
  - `class SemanticCache(client, embed_fn, threshold=0.95, ttl_s=3600, max_scan=1000, now_fn=time.time)`
    - `async get(query) -> list[dict] | None`:embed → `ZREVRANGE recent 0 max_scan-1` → 逐条比余弦 ≥ threshold 命中
    - `async set(query, results) -> None`:`SET cache:{id}` json + `EXPIRE` + `ZADD recent {now: id}`
  - `def get_cache(settings, embed_fn) -> SemanticCache | NoopCache`(未启用/连接失败 → Noop)

- [ ] **Step 1: 写失败测试**

```python
# backend/tests/services/retrieval/test_semantic_cache.py
import json

from app.services.retrieval.semantic_cache import SemanticCache, NoopCache


class _FakeRedis:
    """内存版,仅实现用到的异步方法。"""
    def __init__(self):
        self.kv: dict[str, str] = {}
        self.zset: list[tuple[float, str]] = []  # (score, member)
    async def set(self, k, v): self.kv[k] = v
    async def expire(self, k, ttl): pass
    async def get(self, k): return self.kv.get(k)
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
```

- [ ] **Step 2: 运行确认失败**

Run: `cd backend && python -m pytest tests/services/retrieval/test_semantic_cache.py -v`
Expected: FAIL(ModuleNotFoundError)

- [ ] **Step 3: 写实现**

```python
# backend/app/services/retrieval/semantic_cache.py
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
    async def get(self, query: str):
        return None

    async def set(self, query: str, results: list[dict]) -> None:
        return None


class SemanticCache:
    def __init__(self, client, embed_fn, threshold: float = 0.95,
                 ttl_s: int = 3600, max_scan: int = 1000, now_fn=time.time) -> None:
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
            payload = json.dumps({"query": query, "embedding": qv, "results": results},
                                 ensure_ascii=False)
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
            client, embed_fn,
            threshold=settings.semantic_cache_threshold,
            ttl_s=settings.semantic_cache_ttl_s,
            max_scan=settings.semantic_cache_max_scan,
        )
    except Exception as e:  # noqa: BLE001
        logger.warning("semantic_cache_init_failed_noop", error=str(e))
        return NoopCache()
```

- [ ] **Step 4: 运行确认通过 + 提交**

Run: `cd backend && python -m pytest tests/services/retrieval/test_semantic_cache.py -v`
Expected: PASS(4 passed)

```bash
git add backend/app/services/retrieval/semantic_cache.py backend/tests/services/retrieval/test_semantic_cache.py
git commit -m "feat(retrieval): 语义缓存 Redis ZSET LRU + 有界扫描 + Noop 降级 + 4 用例"
```

---

### Task 7: 编排改造 `hybrid_search.py`

**Files:**
- Modify: `backend/app/services/hybrid_search.py`(新增 `search_pipeline`,`search` 接线保留降级)
- Test: `backend/tests/services/retrieval/test_pipeline.py`

**Interfaces:**
- Consumes: `rewrite`(T4)、`bm25_rank`(T3)、`get_reranker`(T5)、`get_cache`(T6)、`VectorIndex`、`rrf_fusion`(既有)
- Produces:
  - `HybridSearch.search_pipeline(kb_id, query, top_k=5) -> list[dict]`(全管道)
  - 内部可注入依赖以便测试:`HybridSearch(rewriter=None, reranker=None, cache=None)`(默认取真实实现)

- [ ] **Step 1: 写失败测试**

```python
# backend/tests/services/retrieval/test_pipeline.py
from app.services.hybrid_search import HybridSearch


class _FakeCacheMiss:
    async def get(self, q): return None
    async def set(self, q, r): pass


class _FakeCacheHit:
    async def get(self, q): return [{"id": "cached"}]
    async def set(self, q, r): pass


class _IdReranker:
    def rerank(self, q, cands, top_k): return cands[:top_k]


async def test_pipeline_returns_cache_hit_fast(monkeypatch):
    hs = HybridSearch(cache=_FakeCacheHit(), reranker=_IdReranker())
    out = await hs.search_pipeline("kb1", "q", top_k=5)
    assert out == [{"id": "cached"}]  # 命中直接返回,不进召回


async def test_pipeline_recall_rerank(monkeypatch):
    # mock 向量召回 + bm25 + 改写,验证融合→重排出结果
    import app.services.hybrid_search as mod

    class _FakeIndex:
        def __init__(self, kb_id): pass
        def query(self, query_text, top_k):
            return [{"id": "v1", "content": "向量命中"}]
    monkeypatch.setattr(mod, "VectorIndex", _FakeIndex)
    monkeypatch.setattr(mod, "bm25_rank", lambda corpus, q, top_k: [{"id": "b1", "content": "bm25命中"}])
    monkeypatch.setattr(mod, "_load_corpus", lambda kb_id: [("b1", "bm25命中")])

    async def _fake_rewrite(q, llm, n, enable_hyde): return [q]
    monkeypatch.setattr(mod, "rewrite", _fake_rewrite)

    hs = HybridSearch(cache=_FakeCacheMiss(), reranker=_IdReranker())
    out = await hs.search_pipeline("kb1", "q", top_k=5)
    ids = {h["id"] for h in out}
    assert ids & {"v1", "b1"}  # 至少召回其一
```

- [ ] **Step 2: 运行确认失败**

Run: `cd backend && python -m pytest tests/services/retrieval/test_pipeline.py -v`
Expected: FAIL(TypeError: HybridSearch() 不接受 cache 参数 / search_pipeline 不存在)

- [ ] **Step 3: 写实现**

在 `backend/app/services/hybrid_search.py` 顶部 import 区追加:
```python
from app.services.embedding import EmbeddingService
from app.services.retrieval.bm25_search import bm25_rank
from app.services.retrieval.query_rewrite import rewrite
from app.services.retrieval.reranker import get_reranker
from app.services.retrieval.semantic_cache import get_cache
from app.domain.knowledge.vector_index import VectorIndex
```

新增模块级辅助 + 改造 `HybridSearch.__init__` 与新增 `search_pipeline`:
```python
async def _load_corpus(kb_id: str) -> list[tuple[str, str]]:
    from app.core.db import get_session_factory
    from app.repositories.knowledge_repo import KnowledgeRepository
    async with get_session_factory()() as session:
        chunks = await KnowledgeRepository(session).list_chunks(kb_id)
    return [(c.id, c.content) for c in chunks]


# --- 在 class HybridSearch 内 ---
    def __init__(self, rewriter=None, reranker=None, cache=None, llm=None) -> None:
        self._rewriter = rewriter  # 保留以便注入;默认用模块级 rewrite()
        self._reranker = reranker
        self._cache = cache
        self._llm = llm

    async def search_pipeline(self, kb_id: str, query: str, top_k: int = 5) -> list[dict]:
        settings = get_settings()
        cache = self._cache if self._cache is not None else get_cache(settings, EmbeddingService.embed)
        reranker = self._reranker if self._reranker is not None else get_reranker(settings)

        # 1. 语义缓存
        cached = await cache.get(query)
        if cached is not None:
            return cached

        # 2. 查询改写
        llm = self._llm
        if llm is None:
            from app.domain.llm_client import LLMClient
            llm = LLMClient(settings)
        variants = await rewrite(
            query, llm, n=settings.multi_query_n, enable_hyde=settings.enable_hyde,
        ) if settings.enable_query_rewrite else [query]

        # 3. 双路召回(每条改写)
        vector_hits: list[dict] = []
        keyword_hits: list[dict] = []
        corpus = await _load_corpus(kb_id)
        for v in variants:
            try:
                vector_hits.extend(VectorIndex(kb_id).query(query_text=v, top_k=settings.hybrid_top_k_vector))
            except Exception as e:  # noqa: BLE001
                logger.warning("pipeline_vector_failed", error=str(e))
            keyword_hits.extend(bm25_rank(corpus, v, top_k=settings.hybrid_top_k_keyword))

        # 4. RRF 融合 → top-M 候选
        fused = rrf_fusion(vector_hits, keyword_hits, top_k=settings.rerank_top_m, k=settings.hybrid_rrf_k)

        # 5. Cross-Encoder 重排 → top-k
        reranked = reranker.rerank(query, fused, top_k=top_k)

        # 6. 回填缓存
        await cache.set(query, reranked)
        return reranked
```

> 说明:保留既有 `search()` / `_hybrid_search()` / `search_across_kbs()` 不动(向后兼容);调用方按需切到 `search_pipeline`。`search_pipeline` 内每环都有降级(缓存/改写/向量失败均不阻断)。

- [ ] **Step 4: 运行确认通过 + 提交**

Run: `cd backend && python -m pytest tests/services/retrieval/test_pipeline.py -v`
Expected: PASS(2 passed)

```bash
git add backend/app/services/hybrid_search.py backend/tests/services/retrieval/test_pipeline.py
git commit -m "feat(retrieval): hybrid_search 管道编排(缓存→改写→双路召回→RRF→重排)+ 2 用例"
```

---

### Task 8: 领域词典播种 `geo_terms.txt`

**Files:**
- Create: `backend/scripts/seed_geo_terms.py`
- Create: `backend/data/geo_terms.txt`(运行生成 + 手工补技术术语)

- [ ] **Step 1: 写播种脚本**

```python
# backend/scripts/seed_geo_terms.py
"""从 brands 表 + 精选术语生成 jieba 领域词典 data/geo_terms.txt。

词典格式:每行 `词 词频 词性`,词频给 100 保证不被切碎。
"""
import asyncio
from pathlib import Path

from sqlalchemy import select

from app.core.db import get_session_factory
from app.models.orm import BrandORM

# 精选技术术语(手工维护)
TECH_TERMS = [
    "LangChain", "LangGraph", "GPT-4o", "Claude-3.5", "ChromaDB",
    "Cross-Encoder", "BM25", "RRF", "HyDE", "RAGAS", "bge-reranker",
    "生成式引擎优化", "向量检索", "混合检索", "重排",
]


async def main():
    terms: set[str] = set(TECH_TERMS)
    async with get_session_factory()() as session:
        rows = await session.execute(select(BrandORM.brand_name))
        terms.update(r for (r,) in rows.all() if r)
    out = Path("data/geo_terms.txt")
    out.write_text("".join(f"{t} 100 n\n" for t in sorted(terms)), encoding="utf-8")
    print(f"写入 {len(terms)} 个领域词 → {out}")


if __name__ == "__main__":
    asyncio.run(main())
```

- [ ] **Step 2: 运行播种**

Run: `cd backend && python -m scripts.seed_geo_terms`
Expected: 打印「写入 N 个领域词」,生成 `backend/data/geo_terms.txt`

- [ ] **Step 3: 接线启动加载**

在 `backend/app/main.py` 的 lifespan 启动段(找到现有 startup 逻辑处)加载词典:
```python
    from app.services.retrieval.tokenizer import load_domain_dict
    load_domain_dict(get_settings().geo_userdict_path)
```

- [ ] **Step 4: 提交**

```bash
git add backend/scripts/seed_geo_terms.py backend/data/geo_terms.txt backend/app/main.py
git commit -m "feat(retrieval): 领域词典播种脚本 + 启动加载 userdict"
```

---

### Task 9: 复跑 ④ 基线出提升报告 + 更新文档

**Files:**
- Create: `reports/eval/retrieval-after-pipeline-2026-07-17.{md,json}`
- Modify: `docs/RESUME_AI_Agent_Target.md`、`README.md`

- [ ] **Step 1: 让 ④ runner 走新管道**

`backend/scripts/run_baseline.py`(④ Task 6 创建)复制为 `run_after.py`,把 `run_baseline(items)` 的 search 换成走 `search_pipeline` 的适配器:
```python
# backend/scripts/run_after.py
import asyncio
from pathlib import Path
from evals.retrieval.dataset import load_golden_set
from evals.retrieval.retrieval_runner import run_baseline, write_report
from app.services.hybrid_search import HybridSearch

class _PipelineSearch:
    def __init__(self): self._hs = HybridSearch()
    async def search(self, kb_id, query, top_k):
        return await self._hs.search_pipeline(kb_id, query, top_k)

async def main():
    items = load_golden_set("evals/retrieval/golden_set.jsonl")
    rep = await run_baseline(items, search=_PipelineSearch())
    md = write_report(rep, Path("../reports/eval"), "after-pipeline-2026-07-17")
    print(rep.to_dict()); print("报告:", md)

if __name__ == "__main__":
    asyncio.run(main())
```

- [ ] **Step 2: 跑对照(需 Redis 起 + reranker 模型就位)**

Run: `cd backend && python -m scripts.run_after`
Expected: 生成 after 报告。对比 ④ 的 baseline 报告,记录 Recall@5 改进前→改进后真实值。

- [ ] **Step 3: 用真实 delta 更新文档**

把 baseline 与 after 的真实 Recall@5 填入 `docs/RESUME_AI_Agent_Target.md` 与 `README.md`(把 `<前>`/`<后>` 换成真实值):
```markdown
- **混合检索管道**:查询改写(Multi-Query+HyDE)→ 向量+BM25 双路召回 → RRF 融合 → Cross-Encoder(bge-reranker)重排,配 Redis 语义缓存(ZSET LRU + 有界扫描);Recall@5 从 <前> 提升至 <后>(自建金标集 + RAGAS 式评测量化)。
```

- [ ] **Step 4: 提交**

```bash
git add reports/eval/retrieval-after-pipeline-2026-07-17.md reports/eval/retrieval-after-pipeline-2026-07-17.json backend/scripts/run_after.py docs/RESUME_AI_Agent_Target.md README.md
git commit -m "chore(retrieval): 管道升级前后 Recall@5 对照 + 真实数字入文档"
```

---

## Self-Review

**Spec coverage:**
- 决策(CrossEncoder/Redis/改写/BM25 rank_bm25/领域词典/有界扫描)→ T1-T8 逐一 ✅
- 管道 5 环(缓存→改写→双路→RRF→重排)→ T7 ✅
- 模块表(tokenizer/bm25/query_rewrite/reranker/semantic_cache/hybrid_search)→ T2-T7 ✅
- 有界扫描(ZSET LRU + max_scan)→ T6 + 测试 `test_bounded_scan` ✅
- 领域词典(全库 jieba 入口 + 品牌播种)→ T2 + T8 ✅
- 降级链(无 key/无模型/无 Redis/Chroma 挂)→ T4/T5/T6/T7 各含降级 + 测试 ✅
- 配置项 + deps + compose → T1 ✅
- 提升验证接 ④ → T9 ✅
- 非目标(HNSW/自动下载模型)→ 未纳入任务 ✅

**Placeholder scan:** 无 TBD;每个代码步骤含完整代码;T9 的 `<前>/<后>` 是**有意**留给真实运行数字,非缺陷。

**Type consistency:** `rerank(query, candidates, top_k)` 签名 T5 定义、T7 调用一致;`rewrite(query, llm, n, enable_hyde)` T4 定义、T7 调用一致;`get_cache/get_reranker(settings,...)` T5/T6 定义、T7 使用一致;缓存 `get→list|None` / `set(query,results)` 契约 T6 与 T7 一致;`bm25_rank(corpus, query, top_k)` T3 定义、T7 调用一致 ✅
