# v0.5 实施启动话术

> **新会话复制下面整段即可启动 v0.5 实施**

---

```
按 D:/GEO2/docs/superpowers/plans/2026-07-10-geo-optimization-agent-v0.5.md
实施 GEO Agent v0.5（~12 个 task：向量检索升级）。

前置条件：v0.1 + v0.2 + v0.3 + v0.4 代码已存在并测试通过。

流程：
1. 调 superpowers:using-superpowers skill
2. 读 plan + specs/2026-07-10-geo-agent-v0.5-design.md
3. 报告读完，问执行方式（subagent-driven / inline）
4. 简体中文回复，Conventional Commits，TDD 严格

约束：
- 复用 v0.1-v0.4 所有基础设施（FastAPI / SQLite / asyncio）
- ChromaDB 嵌入式（不引入独立服务）
- bge-small-zh-v1.5 embedding 模型（本地、~95MB）
- 混合检索：ChromaDB 向量 + SQLite 关键词 + RRF 融合
- 启动时 lazy 向量化（只处理新 chunks）
- ChromaDB 不可用时降级到纯关键词
- v0.4 agent search_knowledge 工具自动升级（接口不变）
- 前端不变（用户无感知）
- 检索数据在 ./data/chroma/（docker-compose 挂载同目录）
```

---

## 关键文件

| 文件 | 路径 | 用途 |
|---|---|---|
| 设计文档 | `docs/superpowers/specs/2026-07-10-geo-agent-v0.5-design.md` | v0.5 做什么 + 为什么 |
| 实施计划 | `docs/superpowers/plans/2026-07-10-geo-optimization-agent-v0.5.md` | ~12 个 task 的 TDD 步骤 |
| 手动清单 | `docs/MANUAL_VERIFICATION_V0.5.md` | 发布前必跑 7 个场景 |

## 关键决策摘要

- **方向转变**：原 ROADMAP v0.5 是"竞品对比 + 行业基准"，**用户重新定位为"向量检索升级"**（竞品对比推到 v0.6+）
- **核心架构**：在 v0.2 之上加 ChromaDB + bge embedding
- **检索策略**：混合（向量 + 关键词 + RRF）
- **降级策略**：ChromaDB 失败 → 纯关键词（不报错）
- **数据一致性**：SQLite + ChromaDB 通过 `pending_index` 标记同步
- **RRF 常数**：k=60（Cormack 论文标准）
- **不引入**：PostgreSQL / Elasticsearch / pgvector（保持单进程）

## 实施注意事项

- **Phase 0 任务 0.1 (依赖)**：chromadb + sentence-transformers；**首次安装下载 ~300MB 库 + 模型**
- **Phase 0 任务 0.2 (EmbeddingService)**：class-level 缓存模型（懒加载），`SentenceTransformer("BAAI/bge-small-zh-v1.5", cache_folder=settings.models_cache_dir)`
- **Phase 0 任务 0.3 (下载模型)**：**模型不在 git**（`backend/data/models/` 加 .gitignore）；本地下载，**Docker 构建时 COPY 进去**
- **Phase 1 VectorIndex**：class-level 缓存 ChromaDB client（thread-safe）；collection name = `kb_{kb_id}`，metadata `hnsw:space: cosine`
- **Phase 2 HybridSearch + RRF**：
  - `rrf_fusion(vector, keyword, top_k, k=60)` 是纯函数
  - `_hybrid_search` 包 try/except，**任何异常 → 降级到 `_keyword_search`**
  - **不能崩**，降级优先于报错
- **Phase 3 KnowledgeRepository**：新增 `search_chunks_hybrid` 方法（**不删** `search_chunks_by_keyword`，留给降级用）
- **Phase 3 ReindexService**：扫描所有 KB，对比 ChromaDB get_all_ids() 找出缺失，batch embed + add
- **Phase 4 main.py lifespan**：在 `load_all_monitor_tasks()` 后加 reindex（顺序：DB init → scheduler → reindex）
- **Phase 4 v0.4 工具升级**：`ToolExecutor._execute_search_knowledge` 把 `search_chunks_by_keyword` 改为 `search_chunks_hybrid`——**2 处改动**（import + 函数调用），不是 1 行
- **Phase 5 E2E**：重点测"semantic match beats keyword-only"（用户搜"长续航"能找到"电池容量"段落）

## 不要做的事

- ❌ 引入 PostgreSQL + pgvector（用户怕重）
- ❌ 引入 Elasticsearch / Qdrant（保持 ChromaDB）
- ❌ 竞品对比（推到 v0.6+）
- ❌ 行业基准（推到 v0.6+）
- ❌ Cross-encoder rerank（推到 v0.5.1）
- ❌ HyDE（推到 v0.5.2）
- ❌ Query rewriting（推到 v0.5.3）
- ❌ 评估体系（v0.6+）
- ❌ 前端新页面（用户无感知）
- ❌ 检索质量调优 UI

## RAG 7 组件对照

v0.5 在企业级 RAG 7 组件中覆盖：
- ✅ 1. 数据管道（向量化）
- ❌ 2. 查询理解（v0.5.x）
- ✅ 3. 多路召回（关键词 + 向量 2 路）
- ⚠️ 4. 多层排序（RRF 轻量；cross-encoder rerank 推到 v0.5.1）
- ✅ 5. 严格生成（v0.4 agent 已做）
- ❌ 6. 持续评估（v0.6+）
- ❌ 7. 闭环优化（v0.6+）

## 测试重点

- EmbeddingService 模型缓存
- VectorIndex CRUD
- RRF 融合算法（特别是"两路都命中"的 chunk 排名）
- ChromaDB 不可用时降级（**关键**）
- ReindexService 跳过已索引 chunks
- v0.4 工具调用 `search_chunks_hybrid` 而不是 `search_chunks_by_keyword`
- 端到端：混合检索召回率高于纯关键词
