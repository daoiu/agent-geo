# GEO Agent Phase 2 — 记忆层向量化 设计

| 字段 | 值 |
|---|---|
| 版本 | 优化路线图 Phase 2 |
| 日期 | 2026-07-13 |
| 状态 | 设计中，待批 |
| 前置 | Phase 1（循环收敛 + 埋点）已上线 |
| 路线图 | `2026-07-13-memory-context-optimization-roadmap.md` |
| 收敛项 | #2 向量化选记忆 + #3 语义去重 + #1（select 换向量 / extract 加门控） |
| 行为等价 | **否**（select 契约变更：LLM → 向量；现有 select 测试需重写） |

---

## 1. 背景与目标

### 1.1 背景

v0.6 P1.6 的 L2 记忆层每个 user turn 多付 **2 次 LLM 往返**：

- `load_relevant_memories` → `select_relevant`：每轮调一次 LLM 选相关记忆（`memory.py:135`）
- `extract`：每轮 turn_complete 后调一次 LLM 蒸馏（`memory.py:217`）

同时项目 v0.5 已建完整向量栈（`EmbeddingService` bge-small-zh-v1.5 512 维 / ChromaDB /
`rrf_fusion`），但 L2 选记忆却绕开它用 LLM。且 `extract` 去重只靠**精确 name 匹配**
（`memory.py:278`），语义重复（"喜欢简洁" vs "回复要精炼"）要攒到 50 条才由
`consolidate` 兜底。

### 1.2 目标

1. **#2** `select_relevant` 改**纯向量 cosine top-k**，删掉每轮那次 LLM 调用
2. **#3** `extract` 去重加**向量近邻判重**（语义重复即时合并/跳过）
3. **#1** `extract` 加**门控**：turn 过短/无新用户信息则跳过，连 LLM 都不调
4. 复用 `EmbeddingService`；向量存 **ChromaDB 单 collection**（用户 7-13 拍板）

### 1.3 范围（In Scope）

| 模块 | 行为 |
|---|---|
| `MemoryVectorIndex`（新） | ChromaDB 单 collection `agent_memories`，scope 存 metadata；add / query(query_embeddings + where=scope) / delete_scope / count_scope / ids_scope |
| `MemoryService.write_memory` | SQLite 写入后双写向量（embed `name。description`） |
| `MemoryService.select_relevant` | 向量检索 top-k，**删 LLM 调用**；失败降级 recency |
| `MemoryService.extract` | 门控（短 turn 跳过）+ 向量近邻去重（叠加原 exact-name） |
| `MemoryService.consolidate` | replace_all 后同步向量（delete_scope + 重加） |
| `_ensure_vectors`（新，lazy 回填） | select 前补齐存量记忆缺失的向量 |
| `Settings` | `memory_dedup_max_distance: float = 0.15` / `memory_extract_min_chars: int = 8` |
| 测试 | 新增向量索引/select/去重/门控/consolidate 同步/回填/降级；**重写**现有 select 相关用例 |

### 1.4 范围外（Out of Scope）

| 项 | 原因 |
|---|---|
| 向量 + 关键词 RRF | 用户拍板纯向量；池小够用 |
| SQLite 存向量列 | 用户拍板 ChromaDB |
| 重要度/近期性/三因子打分 | 原 L2 设计已否决 |
| 修复 `VectorIndex.query` 用 query_texts 的既有不一致 | 属 KB 域，记入 §10 观测，不在本 Phase 改 |
| 工具结果瘦身 / L0 窗口摘要 | Phase 3 |
| `simple_chat` 调用方大改 | extract/consolidate 仍用 simple_chat，仅 select 去 LLM |

## 2. 架构

### 2.1 存储：SQLite 真相源 + ChromaDB 派生索引

```
AgentMemoryORM (SQLite)  ← 真相源，不加向量列
   id (UUID) ──┐
               ├─ 关联 ─→ ChromaDB collection "agent_memories"
               │            id=memory_id
               │            embedding=bge(name。description) 512 维
               └─           metadata={scope, type}
```

- **一致性模型**：SQLite 权威；ChromaDB 可重建（丢了用 `_ensure_vectors` 回填）
- **双写点**：`write_memory`（加）/ `consolidate`（删+加）/ 未来删记忆（删）
- **降级**：任何 ChromaDB 操作失败 → log warning，退回 SQLite-only 行为，不阻塞

### 2.2 检索：纯向量 cosine top-k

```
select_relevant(scope, messages, k=5):
  recent = _recent_user_text(messages)        # 复用现有
  if not recent: return []
  _ensure_vectors(scope)                        # lazy 回填缺失向量
  qv = EmbeddingService.embed([recent])[0]
  hits = MemoryVectorIndex().query(qv, scope, top_k=k)   # [{id, distance}], query_embeddings + where
  return [get_by_id(h["id"]) for h in hits]     # 回 SQLite 取完整记录，保序
  # 向量失败 → 降级：list_by_scope(scope)[:k]（recency）
```

> 注意：用 `query_embeddings=`（预计算 bge 向量），**不用** `query_texts=`，避免
> `VectorIndex.query` 那个"query 走 ChromaDB 默认 ef、与 add 的 bge 向量不一致"的坑。

### 2.3 去重 + 门控

```
extract(scope, messages, session_id):
  recent = _recent_user_text(messages)
  if len(recent.strip()) < memory_extract_min_chars:   # 门控 #1
      return 0                                           # 短 turn 不调 LLM
  candidates = <LLM 蒸馏，同现有>
  for c in candidates:
     if get_by_name(scope, c.name): continue             # 原 exact-name
     cv = embed([f"{c.name}。{c.description}"])[0]        # 语义判重 #3
     nearest = MemoryVectorIndex().query(cv, scope, top_k=1)   # → [{id, distance}]
     if nearest and nearest[0]["distance"] < memory_dedup_max_distance: continue
     write_memory(...)                                    # 双写向量
```

### 2.3.1 关键设计原则

| 原则 | 选择 | 理由 |
|---|---|---|
| 向量存储 | ChromaDB 单 collection + scope metadata | 用户拍板；避免 per-scope collection 爆炸 |
| 检索 | 纯向量 cosine top-k | 用户拍板；池小 |
| query 向量来源 | 显式 `EmbeddingService.embed` + query_embeddings | 与 add 的 bge 一致；绕开 VectorIndex.query 既有坑 |
| 一致性 | SQLite 权威，ChromaDB 可重建 | 双写失败可降级 + lazy 回填 |
| embed 文本 | `name。description` | 简短有代表性；body_md 长会稀释语义 |
| select 失败降级 | recency top-k | 最简；不再回退 LLM |
| 去重失败降级 | exact-name only | 退回现有行为 |

## 3. 数据模型

`AgentMemoryORM` **不变**（不加向量列）。向量只在 ChromaDB。

ChromaDB collection `agent_memories`：

| 字段 | 值 |
|---|---|
| id | memory_id（= AgentMemoryORM.id, UUID） |
| embedding | bge(`name。description`)，512 维，归一化 |
| document | `name。description`（便于调试可读） |
| metadata | `{"scope": scope, "type": type}` |

## 4. 接口规范

### 4.1 `MemoryVectorIndex`（新，`app/domain/agent/memory_vector.py`）

```python
class MemoryVectorIndex:
    _client = None  # 复用 ChromaDB PersistentClient 单例

    def __init__(self) -> None:
        client = self._get_client()   # 同 VectorIndex 的 PersistentClient(settings.chroma_path)
        self._c = client.get_or_create_collection(
            name="agent_memories", metadata={"hnsw:space": "cosine"})

    def add(self, memory_id: str, scope: str, mtype: str,
            text: str, embedding: list[float]) -> None: ...

    def query(self, embedding: list[float], scope: str,
              top_k: int = 5) -> list[dict]:
        """→ [{"id", "distance"}]，按距离升序（越近越相似）。where={"scope": scope}。"""

    def delete_scope(self, scope: str) -> None: ...       # where={"scope": scope}
    def delete_ids(self, ids: list[str]) -> None: ...
    def ids_in_scope(self, scope: str) -> set[str]: ...    # get(where=)，回填 diff 用
```

失败语义：所有方法内部 try/except + log；`query` 失败抛给调用方由其降级，
`add`/`delete` 失败 log 后静默（SQLite 已是真相）。

### 4.2 `MemoryService` 变更签名

保持公开签名不变（`select_relevant` / `extract` / `consolidate` / `write_memory`），
仅内部实现改。`load_relevant_memories` 拼 XML 块逻辑不变。

### 4.3 Settings

```python
memory_dedup_max_distance: float = 0.15   # cosine distance < 此值视为语义重复
memory_extract_min_chars: int = 8          # 最近 user 文本短于此则跳过 extract
```

## 5. 冷启动 / 回填

`_ensure_vectors(scope)`（lazy，幂等）：

```python
sqlite_rows = repo.list_by_scope(scope)
have = MemoryVectorIndex().ids_in_scope(scope)
missing = [r for r in sqlite_rows if r["id"] not in have]
if missing:
    embs = EmbeddingService.embed([f"{r['name']}。{r['description']}" for r in missing])
    for r, e in zip(missing, embs):
        vidx.add(r["id"], scope, r["type"], f"{r['name']}。{r['description']}", e)
```

在 `select_relevant` 检索前调一次。存量（Phase 2 上线前写入的无向量记忆）首次
select 时自动补齐。

## 6. 错误处理 / 降级

| 场景 | 行为 |
|---|---|
| `write_memory` 向量 add 失败 | log warning；SQLite 已写；下次 select 的 `_ensure_vectors` 补 |
| `select_relevant` 向量 query 失败 | 降级 `list_by_scope(scope)[:k]`（recency） |
| `extract` 去重 query 失败 | 降级 exact-name only（现有行为） |
| `consolidate` 向量同步失败 | log；SQLite 已 replace；下次 select 回填 |
| EmbeddingService 加载失败（沙箱无外网/无缓存） | select 降级 recency；extract 降级 exact-name；不崩 |
| ChromaDB collection 维度冲突 | 不会发生（全用 bge 512 维） |

## 7. 文件地图

```
backend/app/
├── core/config.py                      # 改: +2 settings
├── domain/agent/
│   ├── memory_vector.py                # 新: MemoryVectorIndex
│   └── memory.py                       # 改: write/select/extract/consolidate + _ensure_vectors
└── tests/
    ├── test_memory_vector.py           # 新: add/query/delete_scope/ids_in_scope/where 隔离
    ├── test_memory_service.py          # 改: 重写 select 用例(向量), 加去重/门控/降级/回填
    └── test_react_loop_memory_integration.py  # 改: select 不再 mock LLM
```

## 8. 测试

| 层 | 文件 | 用例 |
|---|---|---|
| 向量索引 | `test_memory_vector.py` | add+query 返回近邻；where scope 隔离（A scope 查不到 B）；delete_scope；ids_in_scope；query 距离升序 |
| select | `test_memory_service.py`（重写） | 向量选中最相关；**无 LLM 调用**（断言 simple_chat 未被调）；空 recent → []；向量失败 → recency 降级 |
| 去重 | `test_memory_service.py` | 语义近邻 < 阈值 → 跳过；远 → 写入；exact-name 仍跳过；去重失败 → exact-only |
| 门控 | `test_memory_service.py` | recent < min_chars → return 0 且不调 LLM；≥ → 正常 extract |
| consolidate | `test_memory_service.py` | replace 后向量同步（旧 scope 向量清、新的加） |
| 回填 | `test_memory_service.py` | 存量无向量记忆 select 前被 _ensure_vectors 补齐 |
| 集成 | `test_react_loop_memory_integration.py`（改） | user turn 注入相关记忆走向量路径，不 mock select 的 LLM |

mock 策略：`EmbeddingService.embed` 用 patch 返回确定向量（避免真加载 bge）；
ChromaDB 用真实内存/临时 client（conftest 可给 tmp chroma_path）或 patch MemoryVectorIndex。

## 9. 迁移 / 兼容

- `AgentMemoryORM` 无 schema 变更 → 无 Alembic
- 存量记忆：无向量 → 首次 select lazy 回填，无需手动迁移
- 回滚：删 collection `agent_memories` + 回退代码即可，SQLite 不受影响

## 10. 观测（只记录，不在本 Phase 改）

- **`VectorIndex.query` 用 `query_texts=`**（`vector_index.py:74-79`）：add 传预计算
  bge 512 维，query 却让 ChromaDB 用默认 ef（英文 384 维），两者不一致。KB 域既有问题，
  本 Phase 记忆检索用 `query_embeddings=` 规避；KB 侧修复另开单。
- **匿名 scope 共享**（`anon:<session_id>`）：无 device_id 时向量也按 scope 隔离，行为同 SQLite。

## 11. 决策日志

| 决策 | 选项 | 选择 | 理由 |
|---|---|---|---|
| 向量存储 | SQLite 列+内存 cosine / ChromaDB 单 collection | ChromaDB 单 collection | 用户 7-13 拍板 |
| 检索策略 | 纯向量 / 向量+关键词 RRF | 纯向量 cosine top-k | 用户 7-13 拍板；池小 |
| query 向量 | query_texts / query_embeddings | query_embeddings（预计算 bge） | 与 add 一致，绕开既有坑 |
| embed 文本 | description / name。description / +body | name。description | 简短有代表性 |
| select 降级 | LLM / 关键词 / recency | recency top-k | 最简，删 LLM 目标 |
| 一致性 | 双写强一致 / SQLite 权威+可重建 | SQLite 权威 + lazy 回填 | 向量丢失可恢复，不阻塞 turn |
| 去重阈值 | 硬编码 / Settings | Settings `memory_dedup_max_distance=0.15` | 可调 |
| 门控条件 | 无 / 最近 user 文本长度 | `memory_extract_min_chars=8` | 简单有效，短 turn 无偏好 |

## 12. 退出标准

- [ ] `select_relevant` 零 LLM 调用（断言 simple_chat 未被调用）
- [ ] 语义重复在 extract 阶段被向量近邻拦截合并
- [ ] 短 turn（recent < 8 字）不触发 extract LLM
- [ ] ChromaDB 失败时 select/extract/consolidate 全部优雅降级，不崩
- [ ] 存量无向量记忆首次 select 自动回填
- [ ] 后端全量单测通过（含重写的 select 用例 + 新增用例）
- [ ] 跨 session 偏好复现端到端不回归（L2 核心场景）
- [ ] L0 / L1 行为不变
