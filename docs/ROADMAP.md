# GEO 优化 Agent 产品路线图

> **目的**：跨会话保留项目演进方向，让新会话打开就能知道 v0.1 之后该做什么。

## 总体演进思路

```
v0.1 (诊断)  →  v0.2 (改写)  →  v0.3 (闭环)  →  v0.4 (多用户)  →  v0.5 (行业)  →  v0.6 (SPA)
   │              │              │               │                │              │
  看清问题      给出方案        自动执行         多人协作         行业对标       完整覆盖
```

每完成一个版本，下个版本开始前要：
1. 用 `superpowers:brainstorming` skill 重新对齐需求
2. 写新版本的 spec（`docs/superpowers/specs/YYYY-MM-DD-geo-agent-v0.X-design.md`）
3. 写新版本的 plan（`docs/superpowers/plans/YYYY-MM-DD-geo-agent-v0.X.md`）
4. 沿用 v0.1 的 TDD 流程

---

## v0.1 — GEO 诊断 ✅ 设计 + 实施完成

**目标**：让品牌方看到自己的 GEO 健康度现状

**主要功能**：
- 官网爬虫（Schema、EEAT、结构、新鲜度检测）
- AI 平台实测提及率（DeepSeek / Kimi）
- 5 维度评分卡
- 优化建议清单
- 网页报告 + PDF 下载

**不在 v0.1 范围**：内容改写、自动发布、用户系统、竞品对比

**实施计划**：`docs/superpowers/plans/2026-07-09-geo-optimization-agent-v0.1.md`（28 个 task）

**完成判定**：`docs/MANUAL_VERIFICATION.md` 4 个场景全过 ✅

---

## v0.2 — 基于知识库的内容生成助手 ✅ 设计 + 实施完成

**目标**：在诊断基础上，让品牌方基于自有资料（白皮书、产品手册、FAQ）批量生成可发布文章，并人工审核

**核心新增能力**：

| 模块 | 描述 |
|---|---|
| **知识库管理** | 上传 PDF / Word / MD / TXT 文件，自动解析 + 切片 + 入库 |
| **关键词检索** | jieba 分词 + 词频排序召回 top-k 切片（v0.5 升级 pgvector） |
| **任务调度** | 选知识库 + 主题 + 关键词 + 文章数，Worker 异步生成 |
| **AI 生成** | 基于知识库真实信息生成 Markdown 文章，强制"不得编造" |
| **人工审核** | 审核队列：批准 / 拒绝（带理由）/ 标记需修订 |
| **v0.1 → v0.2 入口** | 报告页一键"基于此诊断创建生成任务"，品牌名预填 |

**架构变化**：
- 新增 5 张表：`knowledge_bases` / `knowledge_documents` / `knowledge_chunks` / `tasks` / `articles`
- 新增 `app/domain/knowledge/`（parser / chunker / retriever）
- 新增 `app/domain/generator/`（prompt_builder / content_writer）
- 新增 `app/tasks/parser_worker.py` + `app/tasks/task_worker.py`（单飞锁）
- 新增 `app/api/knowledge.py` / `tasks.py` / `reviews.py`
- 前端新增 7 个页面（知识库、任务、审核）+ 路由

**数据模型新增**：
- `knowledge_bases` / `knowledge_documents` / `knowledge_chunks` / `tasks` / `articles`

**前置依赖**：v0.1 完成 ✅

**实施完成情况**：
- 后端 144 个测试通过
- 前端 tsc 编译通过
- 实施计划：`docs/superpowers/plans/2026-07-09-geo-optimization-agent-v0.2.md`（26 个 task）
- 手动验证清单：`docs/MANUAL_VERIFICATION_V0.2.md`（8 个场景）

**不再做**（推到 v0.3+）：
- 向量检索（v0.5）
- 多用户管理（v0.4）
- 自动发布到 WordPress / 公众号（v0.3）

---

## v0.3 — 完整闭环（自动发布 + 监测）

**目标**：从"诊断"到"改写"到"发布"到"监测效果"的全链路自动化

**核心新增能力**：

| 模块 | 描述 |
|---|---|
| **WordPress 发布器** | 接入 WordPress REST API，自动发布改写后的内容 |
| **公众号助手** | 接入微信公众号 API，发布草稿到素材库（人工最终确认） |
| **改写效果监测** | 发布后定期（每天/每周）抓 AI 答案，监测提及率变化 |
| **变化趋势图** | 同一品牌多次诊断的趋势对比（柱状图/折线图） |
| **Slack / 邮件通知** | 监测到显著变化时主动通知 |

**架构变化**：
- 新增 `app/connectors/` 目录（wordpress.py、wechat.py 等）
- 新增 `app/services/monitor.py`（定期调度 + AI 答案抓取）
- 前端新增"监测看板"页面
- 引入 Celery + Redis 替代 asyncio 任务（需要定时任务）
- 引入 Playwright 渲染 SPA 页面（v0.6 内容提前）

**数据模型新增**：
- `PublishJob` 表：发布任务、平台、状态、回执
- `MentionSnapshot` 表：每次监测的提及率快照
- `Connector` 表：第三方平台凭证

**前置依赖**：v0.1 + v0.2 完成

**估算工作量**：4-6 周

**关键风险**：
- 第三方平台 API 稳定性（特别是微信公众号）
- LLM 答案的非确定性（监测曲线会有抖动，需要做平滑）
- 合规风险（自动发布涉及内容真实性，3·15 红线）

---

## v0.4 — 多用户 + 权限 + 历史趋势

**目标**：从"个人工具"变成"团队/企业工具"

**核心新增能力**：

| 模块 | 描述 |
|---|---|
| **用户系统** | 注册、登录、密码重置、邮箱验证 |
| **团队/组织** | 多用户归属同一组织，共享报告 |
| **权限模型** | Owner / Admin / Editor / Viewer |
| **报告归属** | 报告属于组织而非个人 |
| **API 限额** | 按组织配额（避免被滥用） |
| **审计日志** | 谁在什么时候看了什么报告 |

**架构变化**：
- 新增 `app/core/auth.py`（JWT + OAuth）
- 新增 `app/models/user.py`、`app/models/org.py`
- 新增 `app/api/auth.py`
- 前端新增登录/注册/团队管理页
- 数据库升级到 PostgreSQL（用户量增长）
- 引入 Redis 做 session 缓存

**数据模型新增**：
- `User`, `Organization`, `Membership`, `AuditLog` 表

**前置依赖**：v0.1 + v0.2 + v0.3 完成

**估算工作量**：3-4 周

**关键风险**：
- 安全（密码、token、权限漏洞）
- 数据隔离（多租户查询必须严格过滤）

---

## v0.5 — 竞品对比 + 行业基准

**目标**：从"看自己"变成"看自己 + 看对手 + 看行业"

**核心新增能力**：

| 模块 | 描述 |
|---|---|
| **竞品监控** | 用户添加竞品品牌，定期生成竞品 GEO 对比报告 |
| **行业基准** | 按行业聚合数据：手机行业的平均提及率、白酒行业的平均分等 |
| **基准定位** | "你的品牌在 XX 行业排前 30%" |
| **行业报告订阅** | 每月生成行业 GEO 趋势报告（需付费） |
| **白皮书 / 行业洞察** | 公开版本（marketing 用） |

**架构变化**：
- 新增 `app/services/benchmark.py`（行业聚合查询）
- 新增 `app/services/competitor.py`（竞品对比）
- 前端新增"竞品看板"
- 数据仓库升级（行业聚合需要 OLAP 能力）
- 引入 Apache Superset 或类似 BI 工具（可选）

**数据模型新增**：
- `CompetitorRelation` 表：品牌与竞品关系
- `IndustryBenchmark` 表：行业聚合指标

**前置依赖**：v0.1 + v0.4 完成

**估算工作量**：4-5 周

**关键风险**：
- 数据稀疏性（小行业可能只有 5 个品牌）
- 商业化（订阅、付费墙）

---

## v0.6 — SPA 渲染 + 高级爬虫

**目标**：让爬虫看到真实内容（包括 React/Vue 渲染后的页面）

**核心新增能力**：

| 模块 | 描述 |
|---|---|
| **Playwright 渲染** | 用真实浏览器渲染 SPA 页面，拿到 JS 执行后的 DOM |
| **登录后爬取** | 处理需要登录的网站（OAuth、Cookie） |
| **PDF 文档解析** | 解析 PDF 内的链接和文本（很多企业的关键信息在 PDF） |
| **多媒体内容提取** | 提取图片 alt、video transcript，作为 GEO 资产 |
| **国际化支持** | 同一品牌的多语言版本分别诊断 |

**架构变化**：
- 引入 Playwright + 浏览器二进制（Docker 镜像变大）
- 新增 `app/domain/playwright_crawler.py`
- 后端服务内存占用增加（每个爬虫实例 ~200MB）
- 可能需要 Browserless.io 等外部服务

**前置依赖**：v0.1 完成（其他版本不强依赖）

**估算工作量**：3-4 周

**关键风险**：
- 浏览器资源消耗（成本）
- 反爬机制（Cloudflare、captcha）
- 法律风险（爬取合规）

---

## 版本决策矩阵

每个版本开始前，问 3 个问题：

| 问题 | 是 → 继续 | 否 → 调整 |
|---|---|---|
| v0.1 真的在用吗？ | 进入 v0.2 | 暂停，重新评估价值 |
| v0.X 投入产出比合理？ | 进入 v0.X+1 | 横向优化 v0.X |
| 有 v0.X+1 的真实需求吗？ | 开始 brainstorm | 维护 + bug fix |

## 已明确的"不做"事项

避免范围蔓延，以下功能**永远不会做**（或推到 v1.0 之后）：

- ❌ 主动 SEO 优化（关键词工具、外链建设）—— 这是 SEO 工具的事
- ❌ 内容代写服务（人工代写）—— 重运营，违背"白帽"
- ❌ 黑帽 GEO 功能（投毒、伪造、批量软文）—— 3·15 红线
- ❌ AI 大模型训练数据投毒 —— 明确拒绝
- ❌ 跨平台账号买卖 —— 灰色地带
- ❌ 内容农场构建 —— 长期会被搜索引擎和 LLM 双双惩罚

## 文档演进规则

每完成一个版本，更新以下文档：

| 文档 | 更新内容 |
|---|---|
| 本 ROADMAP.md | 当前版本标记 ✅，下一版本标记 🎯，更新"不再做"清单 |
| 新版本 spec | 完整设计文档（`docs/superpowers/specs/YYYY-MM-DD-geo-agent-v0.X-design.md`） |
| 新版本 plan | 完整实施计划（`docs/superpowers/plans/YYYY-MM-DD-geo-agent-v0.X.md`） |
| HANDOFF.md | 更新"新会话启动话术"，指向最新版本 |
| README.md | 更新功能列表、版本号 |
| CHANGELOG.md | 记录每个版本变更（从 v0.1 上线时开始维护） |

## 跨会话连续性保障

确保 v0.2、v0.3 工作不会因为会话中断而失去上下文：

1. **每完成一个 Phase** → 立即 commit + 推进 ROADMAP 状态
2. **每完成一个版本** → 更新 HANDOFF.md 指向新版本 spec/plan
3. **每开新会话** → 用 HANDOFF 启动，让 Claude 读 ROADMAP 知道整体方向
4. **遇到 plan 没覆盖的决策** → 写到 `docs/adr/`（架构决策记录）而不是只放在对话里

## 当前状态

- ✅ v0.1 设计 + 实施完成
- ✅ v0.2 设计 + 实施完成
- 🎯 v0.3：等待 v0.2 验证后启动（多站点分发 + LLM 友好站点包 + 爬虫监测）
- 💤 v0.4+：远期规划
