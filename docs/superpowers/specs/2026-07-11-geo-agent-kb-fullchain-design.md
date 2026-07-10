# GEO Agent KB 全链路设计 — v0.6 P1.4

| 项目 | 内容 |
|---|---|
| 版本 | v0.6（Agent 与 KB 全链路联动） |
| 日期 | 2026-07-11 |
| 状态 | 设计已批，待实施（spec 已写，待用户审） |
| 前置 | P1.3（跨 KB 全局 hybrid 召回）已上线 `GET /knowledge/search` |
| 后端变更 | 增 1 个工具 + 改 1 个工具 + 改 1 个 prompt + 增 1 个工具调用薄包装 |
| 前端变更 | **无**（此 PR 不动 UI） |

---

## 1. Context

GEO 智能助手（`/agent`）v0.4 已经接入 4 工具集（diagnose_brand / search_knowledge / generate_article），其中 `search_knowledge` 与 `generate_article` 都要求传 `kb_id`。这给真实业务带来三个痛点：

1. **用户视角**：用户记不清自己上传过的资料库有哪些品牌，只能抽象地说"给我看看"。
2. **LLM 视角**：让 LLM 主动挑 KB 需要把 KB 列表塞进上下文 — 但目前没有任何工具能让 LLM *发现* 有哪些 KB。
3. **召回视角**：v0.4 search 的 `kb_id` 是强必填，LLM 跨库召回要先 4-tool 循环 list 单库。

P1.3 已解决"前端 UX 层跨库召回"与"AI 工具层全局搜"。本 spec 解决剩下的 **agent 工具集层**——让 LLM 能在会话里：
- 列出所有知识库（不需外部提示）
- 可选 `kb_id` 调 search（不传就跨库，传了就单库）
- 把"5 篇生成"拆给 v0.2 TaskCreator，避免在 agent 会话里循环

目标对齐标准企业级 RAG 全链路：**离线 chunking + embedding 入向量库** ／ **在线检索召回 → 注入 prompt → LLM 生成可溯源回答**。

---

## 2. 决策矩阵（已确认）

| 维度 | 选择 | 原因 |
|---|---|---|
| KB 发现方式 | **新增 `list_knowledge_bases` 工具** | 与现有工具同风格；prompt 长度可控；LLM 显式可观察可解释 |
| `list` 返回粒度 | 只返 `[{kb_id, kb_name, doc_count, created_at}]` | YAGNI；要文档名走 search_knowledge(kb_id) |
| 5 篇生成路径 | **1 task + N review** 两步 | 让 v0.2 任务系统接手；不在 agent 会话循环 |
| `search_knowledge` kb_id | **改可选** | 不传跨库走 P1.3，传了走单库 hybrid |
| `create_generation_task` | 新增工具调用 `POST /api/tasks` | 不污染 task 状态机；落库即可 |

---

## 3. 工具集（变更后共 5 个）

| 工具 | 参数 | 实现路径 |
|---|---|---|
| `diagnose_brand` | `brand_name, industry, official_url` | 不动 |
| **`list_knowledge_bases` 🆕** | `(no args)` | 包装 `GET /api/knowledge`（已存在） |
| **`search_knowledge` (改)** | `kb_id?: str, query: str, limit=5` | `kb_id` 缺失 → `HybridSearch.search_across_kbs`(P1.3)；否则 → `repo.search_chunks_hybrid` |
| `generate_article` | 现有字段 | 不动（仍按"单篇草稿"路径） |
| **`create_generation_task` 🆕** | `kb_id, brand, topic, article_count, keywords, style, target_length` | 包装 `POST /api/tasks`（v0.2 已存在） |

## 4. 数据流：业务场景 5 篇生成

```
[user]  给我生成北北云吞的五篇宣传文章
   ↓
[agent turn]
   LLM ReAct 循环:
    1. tool: list_knowledge_bases()
       resp: [{kb_id=kb_1, kb_name="北北云吞", doc_count=1}, ...]
    2. tool: search_knowledge(kb_id="kb_1", query="北北云吞 食材 工艺 门店")
       resp: [{chunk_id, content, kb_id, kb_name="北北云吞",
               doc_id, doc_filename="北北云吞.md", sources:["keyword"]}]
    3. tool: create_generation_task(
              kb_id="kb_1", brand="北北云吞",
              topic="玉林老字号云吞店",
              article_count=5,
              keywords=["云吞","皮薄","马蹄"],
              style="professional")
       resp: {task_id, status:"pending", article_count:5}
   LLM 最终回答:
     "已创建任务（task_id=xxx），5 篇关于北北云吞的草稿正在生成。
      去 /tasks/xxx 审核 → 发布。"
[end turn]
```

**[user] 也可以模糊问**——"我现在有哪些知识库" 或 "陈皮的云吞皮怎么做"：
- 前者：LLM 直接调 `list_knowledge_bases` 答
- 后者：LLM 先 list 看清品牌列表，匹配"北北云吞"后 search，召回相关 chunk 答

---

## 5. 接口形态

### 5.1 `list_knowledge_bases` (no args)

**响应**：
```json
[
  {"kb_id": "fbac45ba-...", "kb_name": "北北云吞", "doc_count": 1,
   "created_at": "2026-07-10T16:35:08Z"}
]
```

**后端复用**：`GET /api/knowledge` 已有（`KnowledgeBase[]`），在 schema 上加 `doc_count` 字段——通过 `docs = await repo.list_documents(kb_id)` 在 `get_kb` 同 SQL 取 N。但 `list` 不存在 — 这次新增：

| 路由 | 状态 |
|---|---|
| `GET /api/knowledge` (list_kbs) | 已存在 — 增 `doc_count`（用单 SQL JOIN 一次性 GROUP BY，避免 N+1） |
| agent 工具 `list_knowledge_bases` | 🆕 在 `tools.py` 注册，内部调 `api.list_knowledge_bases` helper。**不新增 REST** |

**实现边界**：
1. `GET /api/knowledge` 的 `KnowledgeBase` 响应 schema 加 `doc_count: int` — `repository.list_kbs()` 用 `LEFT JOIN knowledge_documents GROUP BY knowledge_bases.id` 一次取所有 doc_count
2. agent 工具 `list_knowledge_bases` 是 Python 函数（不是 HTTP 调用），注册在 `TOOLS` 字典里，复用 v0.4 agent 上下文

### 5.2 `search_knowledge` 改可选 kb_id

```python
class SearchKnowledgeArgs(BaseModel):
    kb_id: str | None = Field(None, min_length=1)  # 可选
    query: str = Field(..., min_length=1, max_length=500)
    limit: int = Field(5, ge=1, le=10)
```

**Tool schema 描述改**：
```
"在指定知识库中搜索相关资料片段。不传 kb_id 时跨所有知识库全局检索；
 但 kb_id 必须对应已存在的知识库。返回最相关的几个资料片段（含 KB 名称、
 来源文档、及向量/关键词命中来源标签）。"
```

**实现分支**（`tool_executor.execute_search_knowledge`）：
```python
if args.kb_id:
    # 单 KB 路径（v0.5 hybrid）
    return await repo.search_chunks_hybrid(args.kb_id, args.query, args.limit)
else:
    # 跨 KB 全局（P1.3）
    return await HybridSearch().search_across_kbs(args.query, top_k=args.limit)
```

每条 hit 统一 schema：`{chunk_id, content, kb_id, kb_name, doc_id, doc_filename, sources}` —— 前者已含元数据，后者自带，无需转换。

### 5.3 `create_generation_task`

```python
class CreateGenerationTaskArgs(BaseModel):
    kb_id: str = Field(..., min_length=1)
    brand: str = Field(..., min_length=1, max_length=100)
    topic: str = Field(..., min_length=5, max_length=500)
    article_count: int = Field(5, ge=1, le=20)
    keywords: list[str] = Field(..., min_length=1, max_length=20)
    style: Literal["neutral","professional","casual"] = "neutral"
    target_length: int = Field(1500, ge=300, le=10000)
```

**Tool schema 描述**：
```
"创建一个内容生成任务（v0.2 TaskCreator）。返回 task_id。
 生成出的 N 篇文章可在 /tasks/{task_id} 详情页审核 → 发布。
 适用场景：用户希望生成 N 篇而非单篇草稿的批量任务。"
```

**实现**：包装 `POST /api/tasks` (`TaskCreate` schema) — 现有 v0.2 接口直接复用。

---

## 6. Agent 行为契约（`prompts.py` 改动）

`AGENT_SYSTEM_PROMPT` 追加一段"知识库使用策略"（约 100 tokens）：

```
【知识库与生成任务的策略】
1. 当用户提到品牌 / 资料库相关问题时：
   - 先调 list_knowledge_bases() 了解可用 KB 与品牌名
   - 按用户提到的品牌选 kb_id（或对模糊/未指明情况走跨库 search_knowledge 不传 kb_id）
   - 再调 search_knowledge(kb_id=?, query=关键实体+意图) 召回 3-5 个 chunk
2. 召回的 chunk 必须显式标注来源（kb_name、doc_filename），引用时附"依据《xxx》（KB:xxx）"。
3. **不要**直接生成多篇文章的循环。生成 N 篇（N>1）应调 create_generation_task(...)，
   由 v0.2 任务系统异步处理；用户在 /tasks 详情页审核。
4. 单篇草稿可继续用 generate_article(...)。
```

`MAX_REACT_ITERATIONS` 从 5 提到 **7**：list + search + create_task 最少 3 步给 LLM 思考留余量。

---

## 7. 文件地图

```
backend/app/domain/agent/
├── tools.py            # 改 — 加 list_knowledge_bases、create_generation_task；
│                       #     search_knowledge schema 改 kb_id 可选；
│                       #     描述文本扩写
├── tool_executor.py    # 改 — execute_search_knowledge 分支 (kb_id 缺失走 HybridSearch)
├── prompts.py          # 改 — AGENT_SYSTEM_PROMPT 追加"知识库使用策略"段
└── react_loop.py       # 改 — MAX_REACT_ITERATIONS 5 → 7

backend/app/repositories/knowledge_repo.py
   — list_kbs() 加 doc_count 字段（或 keep 现状返回 ORM，doc_count 在 tool 层补查）
```

**新增/修改总计**：4 个后端文件。无前端改动，无新 DB schema，无新外部依赖。

---

## 8. 错误处理

| 场景 | 行为 |
|---|---|
| `list_knowledge_bases` 失败（DB 异常） | 工具返 `{error: "..."}`；LLM 后续用空集继续，并告诉用户"知识库列表暂不可用" |
| `search_knowledge(kb_id=不存在)` | 后端 `get_kb() is None` → 422；工具透传；LLM 重选 |
| `search_knowledge(query=空)` | Field 校验 422；LLM 必须先想清楚 query |
| `search_knowledge(kb_id=None)` 但全库无 hit | 工具返 `{hits: []}`；LLM 自处理，提示用户"目前没匹配到资料，是否换个关键词" |
| `create_generation_task(kb_id=不存在)` | 422；LLM 重新走 list → search → create |

**降级策略**：vector 检索失败的 KB 直接丢弃；与 P1.3 一致。

---

## 9. 测试

| 层 | 用例 | 关键断言 |
|---|---|---|
| `list_knowledge_bases` 工具 | `test_list_kbs_tool` | mock `GET /knowledge` 返 3 条 → 工具返 `len==3` 且字段齐 |
| 同上 | `test_list_kbs_empty` | DB 空 → `[]` |
| `search_knowledge` 工具 | `test_search_kb_id_present` | 传 kb_id → 走到 `repo.search_chunks_hybrid`（mock） |
| 同上 | `test_search_kb_id_absent` | 不传 → 走到 `HybridSearch.search_across_kbs`（mock） |
| 同上 | `test_search_unknown_kb_id` | kb_id="bogus" → 工具抛 422 |
| 同上 | `test_search_limit_overflow` | limit=999 → 422 |
| `create_generation_task` 工具 | `test_create_task_happy` | mock `POST /tasks` 返 `{id: t1, status: "pending"}` → 工具返 `{task_id: "t1", article_count:5}` |
| 同上 | `test_create_task_invalid_kb` | kb_id="bogus" → 422 透传 |
| prompts.py | `test_agent_prompt_mentions_list_first` | AGENT_SYSTEM_PROMPT 包含 "list_knowledge_bases" 与 "create_generation_task" 关键词 |
| 端到端（手动） | `test_agent_e2e_5articles`（Playwright + 真实后端） | 用户发"给我生成北北云吞 5 篇"，agent 调用 list → 匹配 kb_1 → search → create_task |

**总计**：9 case。回归 v0.4 agent 测试（120+）确保不破。

---

## 10. 风险与未做

| 风险 / 未做 | 状态 |
|---|---|
| `list_knowledge_bases` 在 KB 极多（>100）时 N+1 查 doc_count | ⚠️ 已规避 — 单 SQL JOIN `GROUP BY knowledge_bases.id` 一次性拿 |
| chunk 注入 LLM prompt 的"隐式上下文"路径（server-side 自动召回） | ❌ **未做** — 用户选 A 而非 B；LLM 自行 tool 决策 |
| 召回 chunk 进 prompt 前的去冗余（MMR / cross-encoder rerank） | ❌ 留 v0.6+ |
| LLM 给出"5 篇"以外的批量场景（如"列出所有已生成任务"） | ❌ 留 v0.6+ |
| `create_generation_task` 后用户返回 agent 说"再加 3 篇" | ⚠️ 留 v0.6+；当前路径需用户走 `/tasks/{id}` UI 加 |

---

## 11. 决策日志

| 决策 | 选项 | 选择 | 理由 |
|---|---|---|---|
| KB 发现机制 | 加 list 工具 / 永久进 prompt / 强制让用户报 kb_id | **list 工具** | prompt 长度可控；与现有工具风格一致；LLM 显式可观察 |
| 5 篇生成 | 循环 generate_article / 一次性 batch / 落 v0.2 任务 | **v0.2 任务** | 已存在 task state machine；不在会话循环 |
| search kb_id | 必填 / 可选 | **可选** | 跨库走 P1.3；单库走 v0.5 |
| `list` 返回粒度 | kb_only / 含 doc 名 / 关键词标签 | **kb_only** | YAGNI；细粒度按需走 search |
| MAX_REACT_ITERATIONS | 保持 5 / 提到 7 | **7** | list + search + create_task 最少 3 步给余量 |

---

## 12. 退出标准

- [ ] 9 单元测试 / 集成测试通过
- [ ] 既有 v0.4 agent 测试（120+）零回归
- [ ] Prompt 改动后人工手测：用户说"模糊查询" → agent 行为符合 §4 数据流
- [ ] docs/CHANGELOG.md 加 P1.4 节
- [ ] docs/HANDOFF_V0.6.md + frontend/docs/DESIGN.md（agent 工具表）同步

---

## 附录 A — 完整 agent 工具集（变更后）

| 工具 | 必填参数 | 可选参数 | 输入示例 |
|---|---|---|---|
| `diagnose_brand` | brand_name, industry, official_url | — | `(小米, 消费电子, https://www.mi.com)` |
| `list_knowledge_bases` | — | — | `()` |
| `search_knowledge` | query | kb_id?, limit=5 | `(kb_1, 云吞皮, 5)` 或 `(云吞皮,)` |
| `generate_article` | kb_id, brand, topic, keywords | style, target_length | 单篇草稿 |
| `create_generation_task` | kb_id, brand, topic, article_count, keywords | style, target_length | `(kb_1, 北北云吞, "云吞店介绍", 5, [云吞,皮薄])` |
