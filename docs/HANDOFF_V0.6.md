# HANDOFF — v0.6 前端全面重设计 (Phase 0 + P1.3)

> 最后更新: 2026-07-11

## 已完成

- **设计系统地基**:tokens + Tailwind + CSS vars + Inter 字体 (`src/lib/tokens.ts`, `tailwind.config.js`, `src/index.css`)
- **公共组件库 (15 个)** in `src/components/ui/`:Button, Input, Select, Textarea, Spinner, FieldWrapper, Card (+5 slots), Badge, EmptyState, Modal, Drawer, ConfirmDialog, Skeleton, SkeletonList, Tooltip, Tabs (+3 slots), Accordion, Stepper
- **流程组件 (6 个)** in `src/components/flow/`:StageCard, LiveSignal, RankBadge, KnowledgeChunkCard, MentionMatrix, ReasoningTrace
- **Layout 组件 (4 个)** in `src/components/layout/`:TopBar (新 Logo), SideNav (7 组 IA), Breadcrumb, LayoutShell, PipelineRail (6 节点底栏, P0 stub 状态)
- **App.tsx 接入**:所有 19 路由保留,新 LayoutShell 包裹,新增 `/settings` 占位
- **62 个单测 + e2e (布局 + a11y)**:全过
- **文档**:`frontend/docs/DESIGN.md` (tokens 速查)
- **CHANGELOG** 增加 v0.6 section

## Phase 1 / P1.3 — 跨 KB 全局 hybrid 召回 (2026-07-11)

> 目标:对齐 RAG 召回语义 — 全语料池召回,不强制传 kb_id,每个命中带来源

- **后端**:
  - `GET /knowledge/search?q=&limit=`(`api/knowledge.py`,**注册在 `/{kb_id}` 之前**以避免 FastAPI 把 `kb_id="search"` 当成真实 KB 拦截)
  - `KnowledgeRepository.search_chunks_all_keywords(keywords, top_k)`(`repositories/knowledge_repo.py`)— 单次 SQL JOIN chunks + documents + bases,跨 KB 关键词打分,返回 (chunk, kb_name, doc_filename)
  - `HybridSearch.search_across_kbs(query, top_k)`(`services/hybrid_search.py`)— 每个 KB 调一次 `VectorIndex.query`(失败降级)+ 一次全局关键词召回 + RRF 融合
  - `GlobalKnowledgeHit`/`GlobalKnowledgeSearchResult`(`models/knowledge.py`)— 含 `score`(RRF fused)、`sources`(subset of `["vector","keyword"]`)
- **前端**:
  - `KnowledgeList.tsx` 顶部新增「跨知识库全文检索」面板 — `<input type="search">` + Enter 触发;命中卡展示 KB 名 badge、文档名、`sources` chip、`score`;每条带「打开知识库 →」链接跳详情
  - `client.ts` + `types/v0.2.ts` 加 `searchKnowledgeGlobal(q, limit)`
- **测试**:
  - 后端 `tests/test_knowledge_global_search.py` — 7 cases
  - 前端 `src/pages/KnowledgeList.test.tsx` — 6 cases
  - 全量:**后端 420 passed / 前端 24 files · 87 passed**

### 手动验证 P1.3

```bash
# 1. 启动
cd backend && uvicorn app.main:app --port 8000 &
cd frontend && npm run dev

# 2. 浏览器开 http://localhost:5173 → 「知识库」
#    - 顶部输入框敲「云吞 马蹄」回车
#    - 命中卡显示「北北云吞」badge、「北北云吞.md」来源、score 数字、keyword chip
#    - 点「打开知识库 →」跳转到 /knowledge/<kb_id>

# 3. 不传 kb_id
curl 'http://localhost:8000/api/knowledge/search?q=%E4%BA%91%E5%90%9E&limit=5'
# 期望 200 + hits[].kb_name != "" 且 hits[].doc_filename != ""

# 4. 错误路径
curl 'http://localhost:8000/api/knowledge/search?q='         # 422
curl 'http://localhost:8000/api/knowledge/search?q=hi&limit=999'  # 422
```

### 注意事项

- **路由顺序**:`/knowledge/search` 在 `app/api/knowledge.py` 注册位置**必须**在 `@router.get("/{kb_id}")` 之前,否则会被当作 `kb_id="search"` 的 KB 详情请求
- **降级**:`VectorIndex` 任意一个 KB 抛异常 → 该 KB 的向量命中丢弃,关键词路径不受影响;全量 chroma 不可用时退化为纯 keyword(行为同单 KB `HybridSearch.search`)
- **缓存键**:前端 `['knowledge-global-search', query]` + `enabled: false` — 仅手动触发(Enter),输入框每次 keystroke 不打后端
- **未实施范围**:跨 KB 的 re-rank(MMR / cross-encoder)、来源 KB 高亮拼接到 RAG prompt、未做 — 留 v0.6+

## Phase 1 / P1.4 — Agent 工具集扩到 5 (2026-07-11)

> 目标:用户提「给我生成北北云吞 5 篇宣传文」,agent 能自己 list → 匹配 → 召回 → 创建任务,**不在会话循环**

- **新增/改动工具**:
  - `list_knowledge_bases`(新,no args)→ `[{kb_id, kb_name, doc_count, created_at}]`;`KnowledgeRepository.list_kbs` 的 `doc_count` 走单 SQL LEFT JOIN GROUP BY(避免 N+1),`KnowledgeBase` schema 加 `doc_count: int = 0`
  - `search_knowledge`(改)`kb_id` 可选:不传 → `HybridSearch.search_across_kbs`(P1.3 跨库);传了 → `repo.search_chunks_hybrid`(v0.5 单库)。返回 shape 统一加 `kb_name`/`doc_filename`/`scope`
  - `create_generation_task`(新)包装 v0.2 `TaskRepository.create_task` + `task_worker.schedule_task`,**不**抛 HumanConfirmation
- **Prompt 策略**:`AGENT_SYSTEM_PROMPT` 追加"知识库使用策略"段 — 先 list 后 search;chunk 引用附 `kb_name`+`doc_filename`;多篇走 create_task 不在循环
- **`MAX_REACT_ITERATIONS`**:5 → 7
- **文档**:spec `docs/superpowers/specs/2026-07-11-geo-agent-kb-fullchain-design.md` / plan `.../plans/2026-07-11-geo-agent-kb-fullchain-plan.md`
- **测试**:后端 **442 passed**(+22);前端不变(spec §7 无前端改动)

### 手动验证 P1.4

```bash
# 起 backend + frontend
cd backend && uvicorn app.main:app --port 8000 &
cd frontend && npm run dev

# 浏览器: http://localhost:5173/agent
# 输入「我有几个知识库？」（应触发 list 工具，回答含「北北云吞」）
# 输入「给我生成北北云吞的 5 篇不同的宣传文」
#   → agent 应 1) list → 2) 匹配 kb_id='fbac45ba-...' → 3) search → 4) create_task
#   → 回答里出现 task_id 和「去 /tasks/<id> 审核 5 篇草稿」
# 去 http://localhost:5173/tasks/<id> 看到 5 篇文章正在生成
```

### 风险

- `list_knowledge_bases` 的 `doc_count` GROUP BY 在数百 KB 量级 SQLite 仍可;千级以上考虑 PostgreSQL
- prompt 策略段(10 行)会侵蚀 system prompt tokens budget;监控 LLM 调用 system prompt 长度

## Phase 1 / P1.5 — 内容生成 agent 化 + 文章消费体验 (2026-07-11)

> 目标:把 v0.5 的 `ContentWriter` 升级为带独立 system prompt 的 agent,文章生成走 RAG 召回 + GEO 共识提示词;用户能在详情页复制/下载文章

### 后端 — ContentWriterAgent (独立 system prompt)

- **`app/domain/generator/system_prompts.py`** 新增:v2 system prompt,基于 26 个 GEO 提示词工程文档(📝 GEO 内容 / 🛠️ GEO 通用与工具 / 📈 GEO 原理 / 🛡️ GEO 风险,共 10 个核心文档)提炼。核心吸收:RTF 框架 + EEAT 原则 + 答案优先(BLUF)+ 原子化模块 + 严禁编造(最高优先级)+ 反模式清单(6 条)
- **`app/domain/generator/content_writer_agent.py`** 新增:`ContentWriterAgent` 类,独立 system role(不再把角色指令塞 user prompt),接口与旧 `ContentWriter` 兼容(`write_article()` / `stream_article()`),流式 yield 增量 chunks
- **`app/domain/generator/prompt_builder.py`** 拆为 `build_user_prompt`(仅任务参数)+ 旧 `build` 兼容 shim
- **`app/tasks/task_worker.py`** 接入:`ContentWriter` → `ContentWriterAgent`(生产路径切换,旧模块保留兼容)

### 后端 — Bug 修复

- **bug**: `content_writer.py` + `diagnosis_service.py` 之前使用裸 `deepseek_base_url`(如 `https://api.minimaxi.com` 无 `/v1`)直接传 `AsyncOpenAI`,404 被吞成空 content,导致"生成失败 / LLM 调用失败"
- **修**:统一走 `_normalize_base_url` 自动补 `/v1`(已在 v0.5 `llm_client.py` 实现,但 content_writer/diagnosis_service 没复用)
- **回归测试**: `tests/test_content_writer.py` 新增 `test_write_article_normalizes_bare_host_base_url`

### 后端 — 文章单篇详情 + 下载 API

- **`app/api/articles.py`** 新增:
  - `GET /api/articles/{id}` — 单篇详情(返回完整 `title` + `content`,复用现有 `Article` pydantic)
  - `GET /api/articles/{id}/download` — Markdown 文件下载(`Content-Type: text/markdown; charset=utf-8` + `Content-Disposition: attachment`,文件名 `{article_id[:8]}-{sanitized_title}.md`,RFC 5987 双格式支持中文)
- **`app/main.py`** 注册 `articles.router`
- **测试**: `tests/test_articles_api.py` 5 cases

### 前端 — 文章详情页 + 复制/下载

- **`src/pages/ReviewArticle.tsx`** 改造:H1 标题独立大字显示(teal 强调线)+ 正文区剥掉首行 H1(避免重复)+ 3 个按钮(📋 复制全文 Markdown / 📄 复制纯文本 / ⬇ 下载 .md)+ `返回任务详情` 链接
- **`src/lib/markdown.ts`** 新增:`stripMarkdown()` — 把 H1-H3 / 链接 / 图片 / 列表 / 引用 / 代码块剥成纯文本(不引第三方),11 测试
- **`src/pages/TaskDetail.tsx`** 改造:文章卡片右边角新增 📋 一键复制按钮(不进详情页也能复制,`stopPropagation` 防误跳转)
- **测试**: `markdown.test.ts` 11 + `ReviewArticle.test.tsx` 6
- **API client 不变**: 前端 `api.getArticle` 已接 `GET /reviews/{id}`(P1.2 已有)

### 手动验证 P1.5

```bash
# 启动
cd backend && uvicorn app.main:app --port 8000 &
cd frontend && npm run dev

# 浏览器: http://localhost:5173/agent
# 输入「给我生成北北云吞的 5 篇不同的宣传文」(走 P1.4 工具链 + P1.5 ContentWriterAgent)
# 去 /tasks/<id> 等 5 篇生成完成(不再 "LLM 调用失败")
# 每条卡片右上有 📋 一键复制按钮
# 点击文章 → /reviews/<id>
#   - H1 标题大字独立显示
#   - 3 个按钮:📋 复制全文 / 📄 复制纯文本 / ⬇ 下载 .md
#   - 点下载得到 {article_id[:8]}-{title}.md 文件
```

### v2 system prompt 的关键设计决策

| 决策 | 选择 | 原因 |
|---|---|---|
| 角色定位 | GEO 内容生成 agent(融合内容策略/GEO 技术/AI 算法三种视角) | v1 占位骨架太单薄;GEO 文档共识是"多视角融合" |
| 框架方法论 | RTF(Role-Task-Format) | GEO提示词生成模板 / 内容工厂 / AI引用率优化 4+ 处共识 |
| 写作范式 | 答案优先(BLUF)+ 原子化模块 | AI友好内容 / 答案空间占领 / GEO文章生成 5 处共识 |
| 反编造规则 | 升级为最高优先级 + 红线 | 改造提示词(4 次警告)+ 白帽合规 + 品牌知识资产 = 5+ 处 |
| 失败兜底 | "参考资料不足" 提示 + 不拒绝任务 | GEO文章生成系统强调"不拒任务";v1 占位骨架已有此规则 |
| 不做的事 | 不强制 Schema.org JSON-LD 输出 | 后端没存/没渲染;加重 LLM 输出负担;留 v3+ |

### 风险

- v2 system prompt 长度(~900 tokens)比 v1(~150 tokens)长 6 倍;监控 LLM 单次成本
- 6 条反模式清单是经验性约束,实际生成质量需要人工抽样验证
- `stripMarkdown` 不处理 HTML 嵌套 / 自定义容器语法;复杂文章可能残留

## 验证

```bash
cd frontend
npm test           # 62 tests pass
npx tsc --noEmit   # 类型检查通过
npm run dev        # 启动后访问 / 看 LayoutShell;访问 /new /tasks /agent 等一切 19 个 URL 仍可走
```

## 已知遗留 (留 P1+)

| 项 | 何时做 | 工时估 |
|---|---|---|
| `usePipelineState` 替换 stub 为真实 5 个 React Query 聚合 | P1 | 1h |
| 各 page 用新组件重写 | P1-P5 | P1(诊断页)+P2(agent)+P3(知识库/生成)+P4(发布/监测) |
| Dark mode | v0.7 (本期只预留 `--color-*` token) | — |
| `/settings` 实际内容 | P1 | 1h |
| PDF 排版调整 (新 token) | P1 | 1h |

## 设计决策登记

| 决策 | 选择 | 原因 |
|---|---|---|
| 设计语言 | 温暖生产力 (Teal + Orange) | 用户定 |
| 重构深度 | 全面重设计 | 用户定 |
| IA 顶层 | 侧边 + 面包屑 | 用户定 |
| 字体 | Inter | 兼容中英文 / Google Fonts 易加载 |
| Logo | 极简 SVG (圆心 + 6 脉冲点) | 表达"多源信息发射中心" |
| PipelineRail 数据 | P0 stub (全 pending),P1 接 5 个 query | 避免引入未测量的 API 形态 |
| Modal 实现 | HTML5 `<dialog>` 原生 | 内置焦点陷阱 / ESC / backdrop,零依赖 |
| 测试框架 | vitest 4 + @testing-library/react 16 | 项目原只有 Playwright,补单元层 |
| a11y 范围 (P0) | 仅 layout shell (header/nav/footer/main) | page 内部违规要等 page 重写 |

## 文件地图

```
frontend/
├── docs/DESIGN.md                                              # 新
├── tailwind.config.js                                          # 改
├── index.html                                                  # 改 (title + Inter)
├── src/
│   ├── App.tsx                                                 # 改 (LayoutShell 接入)
│   ├── index.css                                               # 改 (tokens + base reset)
│   ├── lib/
│   │   ├── tokens.ts                                           # 新
│   │   ├── tokens.test.ts                                      # 新
│   │   ├── usePipelineState.ts                                 # 新 (stub)
│   │   └── utils.ts                                            # 沿用
│   ├── test/
│   │   ├── setup.ts                                            # 新
│   │   ├── renderWithRouter.tsx                                # 新
│   │   └── sanity.test.ts                                      # 新
│   ├── components/
│   │   ├── ui/         (15 个公共组件 + 测试)
│   │   ├── flow/       (6 个流程组件 + 测试)
│   │   └── layout/     (4 个 layout 组件 + PipelineRail + 测试)
│   ├── pages/          (全部沿用,内部样式 P1+ 升级)
│   ├── api/client.ts                                          # 沿用
│   └── types/                                                 # 沿用
└── tests/e2e/
    ├── diagnosis-flow.spec.ts                                  # 改 (brand 名 + 加 P0 用例)
    ├── p0-layout-shell.spec.ts                                 # 新
    └── p0-a11y.spec.ts                                         # 新
```

## 提交记录 (本次 PR 涉及 commits)

```
fix(backend): anchor .env to project root + strict Settings validator
chore(frontend/v0.6/P0): vitest+RTL+axe infra, renderWithRouter helper
feat(frontend/v0.6/P0): design tokens (Tailwind+CSS vars+Inter+tests)
feat(frontend/v0.6/P0): Button, Input, Select, Textarea, Spinner, FieldWrapper
feat(frontend/v0.6/P0): Card (+slots), Badge, EmptyState (+DefaultEmptyIllustration)
feat(frontend/v0.6/P0): Modal+Drawer+ConfirmDialog, Skeleton+Tooltip+Tabs+Accordion, Stepper
feat(frontend/v0.6/P0): flow components — StageCard, LiveSignal, RankBadge, KnowledgeChunkCard, MentionMatrix, ReasoningTrace
feat(frontend/v0.6/P0): LayoutShell + TopBar + SideNav + Breadcrumb + PipelineRail (stub state)
feat(frontend/v0.6/P0): App.tsx mounts LayoutShell + navItems + crumbsFor mapper
test(frontend/v0.6/P0): e2e — LayoutShell smoke + a11y axe (header/nav/footer/main)
docs(frontend/v0.6/P0): DESIGN.md tokens guide + CHANGELOG + HANDOFF_V0.6
feat(backend/v0.6/P1.4): agent 工具集扩到 5 + 知识库使用策略
feat(backend/v0.6/P1.4): KnowledgeBase.doc_count 单 SQL JOIN
docs(v0.6/P1.4): CHANGELOG + HANDOFF + DESIGN 同步 P1.4 完成
feat(backend/v0.6/P1.5): ContentWriterAgent 独立 system prompt + base_url 修复
feat(backend/v0.6/P1.5): GET /articles/{id} + 下载 .md
feat(frontend/v0.6/P1.5): ReviewArticle 详情页 H1 区分 + 复制/下载
feat(frontend/v0.6/P1.5): TaskDetail 卡片 📋 一键复制
docs(v0.6/P1.5): CHANGELOG + HANDOFF 同步 P1.5 完成
```

## 退出标准

✅ P0 退出:62 单测 + 5 layout 单测 + Playwright 2 e2e spec 全部通过 + TS strict 通过 + dev server 启动 19 路由可达 + 全 visual 上能看到新 TopBar + SideNav + 6 节点底栏 + 面包屑。

下一阶段入口:P1 仪表盘 + 诊断流程可视化(StageCard + LiveSignal + PipelineRail 真数据)。
