# 设计:① 混合检索管道升级

> 日期:2026-07-17
> 范围:本 spec 只覆盖「① 混合检索管道」子系统。④评测基准(已出 spec)/②Agent 编排反思 / ③OCR+VLM 各自另立 spec。
> 依赖前置:量化提升依赖 ④ 的评测基准(`backend/evals/retrieval/`)先落地并跑出改进前基线。

## 背景与目标

现有检索链路(`backend/app/services/hybrid_search.py`)为「ChromaDB 向量 + jieba 裸关键词计数 → RRF 融合」,其中:

- "关键词"是 `chunk.content.count(kw)` 裸子串计数(`knowledge_repo.search_chunks_by_keyword`),**不是 BM25**。
- **无查询改写、无重排、无缓存**。
- 本地仅有 `bge-small-zh-v1.5`,**无 reranker 模型**;项目**无 Redis**。

目标:升级为「**查询改写 → 向量 + BM25 双路召回 → RRF 融合 → Cross-Encoder 重排**」,外层套**语义缓存**,并用 ④ 的评测基准量化 Recall@5 提升(简历「0.61 → 0.83」的改进后数字来源)。

## 决策记录(来自澄清)

- **Cross-Encoder**:真 `bge-reranker-base`(用户在有网环境预下,放 `backend/data/models/`);`Reranker` 协议抽象,可切换;无模型时降级为恒等重排。
- **语义缓存**:真 Redis(`redis` / redis-py + `docker-compose` 加 redis 服务);按 query embedding 余弦相似度命中;单测 mock,集成测试 gated(`REDIS_URL` 不可达自动 skip)。
- **查询改写**:Multi-Query 默认开 + HyDE 可配置(settings 开关);无 LLM key 时降级为原查询。
- **BM25**:使用 `rank_bm25` 库(`BM25Okapi`,纯 Python),jieba 分词喂语料;替换现有裸计数。需在 `pyproject.toml` 加依赖 `rank-bm25`。
- **顺序**:本子系统(①)在 ④ 之后做。

## 管道与模块边界

尽量新增独立模块,少动 `hybrid_search.py` 主体。

| 模块 | 职责 | 状态 |
|---|---|---|
| `backend/app/services/retrieval/query_rewrite.py` | LLM 生成 N 条 Multi-Query 改写 + 可选 HyDE 假设文档;无 key 降级为 `[原查询]` | 新增 |
| `backend/app/services/retrieval/bm25_search.py` | 用 `rank_bm25.BM25Okapi` 打分,jieba 分词;对 KB chunk 语料排序取 top-k | 新增 |
| `backend/app/services/retrieval/reranker.py` | `Reranker` 协议 + `CrossEncoderReranker`(bge-reranker,本地加载,单例)+ `IdentityReranker`(无模型降级) | 新增 |
| `backend/app/services/retrieval/semantic_cache.py` | `SemanticCache`(Redis 后端)+ 语义命中(embedding 余弦 ≥ 阈值)+ TTL;无 Redis 时 no-op | 新增 |
| `backend/app/services/hybrid_search.py` | 编排:缓存查 → 改写 → 双路召回 → RRF → 重排 → 缓存写。保留现有降级链 | 改造 |

**边界原则**:bm25 纯计算;reranker / cache 各自单例 + 降级;query_rewrite 只依赖 `llm_client`;hybrid_search 只做编排。每个可独立单测。

## 数据流

```
query
 → semantic_cache.get(query)   命中(余弦 ≥ 阈值)→ 直接返回(<50ms 快路径)
 → query_rewrite: [原查询] + Multi-Query N 条 (+ 可选 HyDE 假设文档)
 → 对每条改写: 向量召回(VectorIndex.query) + BM25 召回(bm25_search)
 → RRF 融合(所有召回列表)         → top-M 候选(如 M=20)
 → Cross-Encoder 重排候选          → top-k(如 k=5)
 → semantic_cache.set(query, 结果)
 → 返回
```

## 关键实现要点

- **语义缓存命中**:进来的 query 先 embed(复用 `EmbeddingService`),与 Redis 中近期缓存的 query 向量比余弦,≥阈值即命中返回缓存结果。这是简历「延迟 <50ms / 降 90%」的来源(命中路径跳过 LLM 改写 + 重排)。存储:query 文本、embedding、结果 JSON,带 TTL。
- **BM25**:`bm25_search` 载入 KB chunk,jieba 分词构 `BM25Okapi`,对 query 分词 `get_scores` 排序取 top-k。语料构建可按 KB 缓存(与向量召回并列作为一路)。
- **Cross-Encoder**:对 RRF 后的 top-M 候选 `(query, chunk_content)` 打分重排取 top-k;`sentence_transformers.CrossEncoder` 从 `settings.models_cache_dir` 本地加载,单例缓存。
- **降级链(全程「绝不 5xx」)**:无 LLM key → 跳过改写 / HyDE;无 reranker 模型 → `IdentityReranker`;无 Redis → 缓存 no-op;Chroma 失败 → 退关键词。任一环坏,管道仍出结果。

## 配置(settings 新增,均带默认值,缺省 = 当前行为的平滑升级)

- `enable_query_rewrite: bool = True`
- `enable_hyde: bool = False`
- `multi_query_n: int = 3`
- `rerank_top_m: int = 20`
- `rerank_enabled: bool = True`
- `rerank_model_name: str = "BAAI/bge-reranker-base"`
- `semantic_cache_enabled: bool = True`
- `semantic_cache_threshold: float = 0.95`
- `semantic_cache_ttl_s: int = 3600`
- `redis_url: str = "redis://localhost:6379/0"`

## 错误处理 & 测试

- **单测**(离线可跑):`bm25_search` 打分正确性;`query_rewrite` mock LLM + 无 key 降级;`reranker` mock / 恒等降级;`semantic_cache` mock redis + 语义命中 / 未命中 / TTL;`hybrid_search` 编排(mock 各依赖,验证降级链)。
- **集成测试**(gated):reranker 真模型(模型存在才跑,否则 skip);Redis(`REDIS_URL` 可达才跑,否则 skip)。
- **提升验证**:接 ④ 的 `retrieval_runner`,升级前后各跑一次,report 出 Recall@5 / MRR@5 delta。

## 交付物

1. `backend/app/services/retrieval/` 全套模块 + 单测。
2. `hybrid_search.py` 改造为新管道 + 保留降级。
3. `pyproject.toml` 加 `rank-bm25` 依赖;`docker-compose.yml` 加 redis 服务;`.env.example` 加新配置项。
4. 升级后复跑 ④ 基线,产出 Recall@5 提升报告。

## 非目标(明确排除)

- 评测框架本身(④ 已覆盖)。
- ② Agent 编排反思;③ OCR / VLM。
- RediSearch 向量索引(语义缓存用简单余弦扫描近期条目即可,当前规模够用)。
- reranker 模型的自动下载(用户手动预下)。
