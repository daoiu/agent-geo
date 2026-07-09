# GEO 优化 Agent v0.1 设计文档

| 字段 | 值 |
|---|---|
| 日期 | 2026-07-09 |
| 版本 | v0.1 (MVP) |
| 状态 | 设计阶段 |
| 作者 | Claude (brainstorming session) |

## 1. 背景与目标

### 1.1 背景

随着生成式 AI 搜索（豆包、DeepSeek、Kimi、通义千问等）取代传统搜索引擎成为用户获取信息的首选入口，品牌方需要一个工具来诊断"我的内容在 AI 答案里被引用的程度如何"。

GEO（Generative Engine Optimization，生成引擎优化）是 2024 年由 IIT Delhi + 普林斯顿学者提出的优化框架，目标是让品牌内容在 AI 生成答案中被优先引用。

当前 GEO 服务市场存在两类问题：
1. **黑帽 GEO**（投毒式 GEO）通过批量伪造软文操纵 AI 输出，已被 2026 年 3·15 晚会曝光为黑色产业链
2. **白帽 GEO 工具缺位**：能让品牌方系统化诊断自身 GEO 健康度的工具几乎没有

本项目定位为**白帽 GEO 诊断工具**，只做诊断和优化建议，不做内容伪造/发布/操纵。

### 1.2 目标

为非技术市场人员提供一个 Web 应用：
- 输入品牌基本信息 → 自动生成 GEO 健康度诊断报告
- 报告覆盖：AI 提及率、五维度评分、可执行优化建议
- 报告可在线查看 + PDF 下载

### 1.3 范围（In Scope）

- 诊断官网的可爬取性（robots.txt、Schema、结构化）
- 评估内容 E-E-A-T 信号
- 在 1-2 个国产 LLM 平台上查询品牌提及率
- 生成五维度评分卡
- 输出可执行优化建议
- 生成 PDF 报告下载

### 1.4 范围外（Out of Scope, MVP 不做）

- 用户系统、鉴权、多租户
- 公开分享 URL（报告页只在应用内可看）
- 内容自动改写/发布
- 多平台 LLM 横向对比（先支持 1-2 个，后续扩展）
- 历史报告对比 / 趋势分析
- 邮件通知
- Playwright 渲染（SPA 网站爬不到的内容）
- 数据可视化看板
- 移动端原生应用

## 2. 用户与场景

### 2.1 目标用户

**非技术市场人员**（如品牌运营、SEO/GEO 从业者、企业市场负责人）

特征：
- 懂业务不懂技术（不熟悉 HTML、Schema、robots.txt 等技术概念）
- 需要友好的引导式 UI，不能直接面对 JSON 或 DevTools
- 报告术语需业务化（"结构化数据完整度"而非"JSON-LD 覆盖率"）
- 希望快速理解结论并采取行动

### 2.2 核心使用场景

**场景：品牌运营人员诊断自家品牌 GEO 健康度**

```
1. 打开应用 → 点击"开始诊断"
2. 填写 3 步表单：
   - 步骤 1：品牌名 + 行业 + 官网 URL
   - 步骤 2：3-5 个目标用户问题
   - 步骤 3：（可选）竞品列表 + 邮箱
3. 提交 → 进入进度页（轮询状态）
4. 60-90 秒后任务完成 → 自动跳转到报告页
5. 查看报告：五维度雷达图、AI 提及率、优化建议清单
6. 下载 PDF 报告分享给领导/客户/团队
```

### 2.3 成功标准

- 提交表单到看到报告，**90 秒内完成**
- 报告内容让非技术用户能直接理解"我应该做什么"
- 单机部署，docker-compose 一键启动

## 3. 架构总览

### 3.1 系统组件图

```
┌──────────────────────────────────────────────────────────────┐
│  浏览器（React SPA）                                          │
│  ┌──────────┐  ┌──────────────┐  ┌──────────────┐           │
│  │ 表单向导  │→│ 加载/进度页  │→│  报告查看页   │           │
│  │ (3 步)  │  │ (轮询状态)  │  │ (含图表+PDF)  │           │
│  └──────────┘  └──────────────┘  └──────────────┘           │
└──────────────────────────┬───────────────────────────────────┘
                           │ JSON REST API
┌──────────────────────────▼───────────────────────────────────┐
│  FastAPI 应用（单进程）                                       │
│  ┌─────────────────────────────────────────────────────┐    │
│  │ API 路由层（presentation）                          │    │
│  │  /api/diagnosis  /status  /report  /pdf  /list      │    │
│  └─────────────────┬───────────────────────────────────┘    │
│                    │                                          │
│  ┌─────────────────▼───────────────────────────────────┐    │
│  │ 服务层（application）                                │    │
│  │  DiagnosisService（编排诊断流程）                    │    │
│  │  ReportService（生成 HTML / PDF）                    │    │
│  └─────────────────┬───────────────────────────────────┘    │
│                    │                                          │
│  ┌─────────────────▼───────────────────────────────────┐    │
│  │ 领域层（domain）                                     │    │
│  │  Crawler（页面爬取）  LlmClient（LLM 调用）           │    │
│  │  Scorer（评分引擎）   Renderer（HTML/PDF 模板）       │    │
│  └─────────────────────────────────────────────────────┘    │
│                                                              │
│  异步任务：asyncio.Task 后台跑诊断                            │
│  持久化：SQLite (aiosqlite)                                  │
└──────────────────────────────────────────────────────────────┘
```

### 3.2 架构决策

| 决策 | 选择 | 理由 |
|---|---|---|
| 前后端分离 | 完全分离（React + FastAPI JSON） | 现代 Web 标准、解耦清晰 |
| 部署形态 | 单体 FastAPI + asyncio 后台任务 | MVP 阶段避免 Celery/Redis 复杂度 |
| 数据存储 | SQLite | 单机部署够用，零配置 |
| 任务队列 | asyncio.Task + 状态写 SQLite | 简单，避免引入 Celery |
| 并发控制 | asyncio.Lock（同时只跑 1 个诊断） | 避免 LLM API 配额超限 |
| LLM 选型 | DeepSeek + Kimi（OpenAI 兼容协议） | 国产、价格友好、中文强 |
| PDF 渲染 | 后端 WeasyPrint | CJK 字体好处理、样式完整 |
| 报告 HTML | React 渲染（前后端分离） | Jinja2 仅用于 PDF 模板后端内部 |

### 3.3 后端目录结构

```
backend/
├── app/
│   ├── main.py                 # FastAPI 入口
│   ├── api/
│   │   ├── diagnosis.py        # 诊断相关路由
│   │   └── reports.py          # 报告查看 / PDF 下载
│   ├── core/
│   │   ├── config.py           # 配置（API key 等）
│   │   └── db.py               # SQLite 初始化
│   ├── domain/
│   │   ├── crawler.py          # 网页爬取
│   │   ├── llm_client.py       # DeepSeek/Kimi 封装
│   │   ├── scorer.py           # 五维度评分逻辑
│   │   ├── renderer.py         # HTML / PDF 模板渲染
│   │   └── exceptions.py       # 领域异常类
│   ├── services/
│   │   ├── diagnosis_service.py # 编排诊断流程
│   │   └── report_service.py   # 报告存储 / 检索
│   ├── models/
│   │   ├── diagnosis.py        # Pydantic 模型
│   │   └── report.py
│   ├── tasks/
│   │   └── worker.py           # asyncio 后台任务
│   └── templates/
│       ├── report.html.j2      # PDF 用 HTML 模板
│       └── report.pdf.css      # PDF 样式
├── tests/
│   ├── test_crawler.py
│   ├── test_scorer.py
│   ├── test_diagnosis_service.py
│   └── test_api.py
├── data/
│   └── reports.db              # SQLite 文件
├── requirements.txt
└── Dockerfile
```

### 3.4 前端目录结构

```
frontend/
├── src/
│   ├── pages/
│   │   ├── NewDiagnosis.tsx    # 多步表单向导
│   │   ├── DiagnosisStatus.tsx # 进度页
│   │   ├── ReportView.tsx      # 报告查看
│   │   └── ReportList.tsx      # 历史报告列表
│   ├── components/
│   │   ├── WizardStep.tsx
│   │   ├── ScoreChart.tsx      # 雷达图（recharts）
│   │   ├── BrandMentions.tsx   # 提及率可视化
│   │   └── SuggestionCard.tsx  # 优化建议卡片
│   ├── api/
│   │   └── client.ts           # fetch 封装
│   ├── types/
│   │   └── diagnosis.ts
│   ├── App.tsx
│   └── main.tsx
├── tests/
│   └── e2e/
│       └── diagnosis-flow.spec.ts
├── index.html
├── package.json
├── vite.config.ts
└── Dockerfile
```

### 3.5 部署结构

```
D:/GEO2/
├── docker-compose.yml          # 一键启动 backend + frontend
├── README.md
├── .env.example                # API key 等配置示例
├── backend/                    # 见 3.3
├── frontend/                   # 见 3.4
└── docs/
    └── superpowers/
        └── specs/
            └── 2026-07-09-geo-optimization-agent-design.md  # 本文档
```

### 3.6 技术栈清单

| 层 | 选型 |
|---|---|
| 后端框架 | FastAPI 0.115+ (async) |
| 后端 ASGI | Uvicorn |
| 异步 HTTP | httpx |
| HTML 解析 | selectolax（轻量、快） |
| LLM 客户端 | openai SDK（兼容 DeepSeek/Kimi 的 OpenAI 协议） |
| 数据验证 | Pydantic v2 |
| 数据库 | SQLite + aiosqlite + SQLAlchemy 2.0 async |
| PDF 渲染 | WeasyPrint |
| 模板引擎 | Jinja2（仅 PDF 模板使用） |
| 前端框架 | React 18 + TypeScript + Vite |
| 前端路由 | React Router 6 |
| 前端 UI | Tailwind CSS + shadcn/ui |
| 前端图表 | Recharts |
| 前端状态 | TanStack Query (React Query) |
| 容器化 | Docker + docker-compose |
| 后端测试 | pytest + pytest-asyncio + httpx |
| 前端测试 | Vitest + React Testing Library + Playwright |

## 4. 数据模型

### 4.1 核心实体关系

```
DiagnosisRequest (用户输入)
       ↓
DiagnosisTask (异步任务状态)
       ↓
Report (最终报告)
   ├── BrandInfo (品牌信息)
   ├── MentionResult[] (AI 提及率结果，每个问题一个)
   ├── SiteAudit (站点审计)
   │    ├── SchemaCoverage
   │    ├── EeatSignals
   │    ├── StructureScore
   │    ├── FreshnessScore
   │    └── PerformanceSignals
   ├── ScoreCard (五维度总分)
   └── Suggestion[] (优化建议)
```

### 4.2 Pydantic 模型

```python
# models/diagnosis.py

class DiagnosisRequest(BaseModel):
    """用户提交的多步表单聚合"""
    brand_name: str
    industry: str
    official_url: HttpUrl
    target_questions: list[str]        # 3-5 个典型用户问题
    competitors: list[str] = []
    contact_email: EmailStr | None


class TaskStatus(str, Enum):
    PENDING = "pending"
    CRAWLING = "crawling"
    QUERYING_LLM = "querying_llm"
    SCORING = "scoring"
    RENDERING = "rendering"
    COMPLETED = "completed"
    FAILED = "failed"


class DiagnosisTask(BaseModel):
    id: str                            # UUID
    request: DiagnosisRequest
    status: TaskStatus
    progress: int                      # 0-100
    error_message: str | None
    created_at: datetime
    updated_at: datetime


class MentionResult(BaseModel):
    """单个问题的 AI 提及率结果"""
    question: str
    llm_provider: str                  # "deepseek" | "kimi"
    llm_answer: str
    brand_mentioned: bool
    mention_position: int | None       # 1-based
    competitors_mentioned: list[str]
    sentiment: Literal["positive", "neutral", "negative"]
    error: str | None = None           # 失败时填入，不计入 mention_rate


class SchemaCoverage(BaseModel):
    has_organization: bool
    has_website: bool
    has_faq: bool
    has_article: bool
    has_breadcrumb: bool
    has_product: bool
    detected_schemas: list[str]


class EeatSignals(BaseModel):
    has_author_bio: bool
    has_contact_page: bool
    has_about_page: bool
    third_party_mentions: int
    has_expert_attribution: bool


class StructureScore(BaseModel):
    h1_count_ok: bool
    heading_hierarchy_valid: bool
    has_lists_or_tables: bool
    avg_paragraph_length: int
    bluf_score: float                  # 0-1


class FreshnessScore(BaseModel):
    last_modified: datetime | None
    days_since_update: int | None
    has_publish_date: bool
    has_recent_mention_in_content: bool


class SiteAudit(BaseModel):
    url: str
    crawl_status: Literal["success", "partial", "failed"]
    crawled_at: datetime
    schema: SchemaCoverage
    eeat: EeatSignals
    structure: StructureScore
    freshness: FreshnessScore
    page_load_ms: int | None
    robots_txt_allows_ai_bots: dict[str, bool]


class DimensionScore(BaseModel):
    name: str
    score: float                       # 0-10
    weight: float                      # 0-1
    evidence: list[str]


class ScoreCard(BaseModel):
    authority: DimensionScore
    relevance: DimensionScore
    structure: DimensionScore
    freshness: DimensionScore
    verifiability: DimensionScore
    overall: float                     # 0-100
    mention_rate: float                # 0-1
    avg_mention_position: float | None


class Suggestion(BaseModel):
    priority: Literal["P0", "P1", "P2"]
    category: str
    title: str
    detail: str
    action_steps: list[str]
    expected_impact: str


class Report(BaseModel):
    id: str
    task_id: str
    brand: BrandInfo
    site_audit: SiteAudit | None
    mentions: list[MentionResult]
    score_card: ScoreCard
    suggestions: list[Suggestion]
    summary: str                       # LLM 生成的执行摘要
    created_at: datetime
```

### 4.3 SQLite 表结构

```sql
CREATE TABLE reports (
    id              TEXT PRIMARY KEY,           -- UUID
    task_id         TEXT NOT NULL UNIQUE,
    brand_name      TEXT NOT NULL,
    industry        TEXT NOT NULL,
    official_url    TEXT NOT NULL,
    status          TEXT NOT NULL,
    progress        INTEGER DEFAULT 0,
    error_message   TEXT,
    request_json    TEXT NOT NULL,
    report_json     TEXT,
    pdf_path        TEXT,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_reports_created_at ON reports(created_at DESC);
CREATE INDEX idx_reports_brand_name ON reports(brand_name);
```

### 4.4 存储策略

| 数据 | 存储方式 |
|---|---|
| 报告元数据 | SQLite 字段 |
| `DiagnosisRequest` 完整内容 | JSON 字段 `request_json` |
| `Report` 完整内容 | JSON 字段 `report_json`（任务完成后写入）|
| PDF 文件 | `data/reports/{report_id}.pdf` 本地文件 |

**MVP 不做用户系统**，所有报告共享一个列表。

## 5. 诊断流程

### 5.1 端到端时序

```
用户          React 前端           FastAPI          asyncio Task            LLM/爬虫
 │                │                   │                   │                     │
 │ 提交表单       │                   │                   │                     │
 ├───────────────>│                   │                   │                     │
 │                │ POST /diagnosis   │                   │                     │
 │                ├──────────────────>│                   │                     │
 │                │ 202 + task_id     │                   │                     │
 │                │<──────────────────┤                   │                     │
 │                │                   │ 启动后台 task      │                     │
 │                ├───────────────────┼──────────────────>│                     │
 │                │ GET /status       │                   │ 阶段 1: 爬虫         │
 │                ├──────────────────>│                   │ status=crawling      │
 │                │                   │                   ├──────爬官方 URL─────>│
 │                │                   │                   │ 阶段 2: LLM 并行     │
 │                │                   │                   ├────问问题 N─────────>│
 │                │                   │                   │ 阶段 3: 评分         │
 │                │                   │                   │ 阶段 4: 渲染         │
 │                │ GET /report/{id}  │                   │ status=completed     │
 │                ├──────────────────>│ Report JSON       │                      │
 │                │ GET /report/{id}/pdf                  │                      │
 │                ├──────────────────>│ stream PDF        │                      │
```

### 5.2 各阶段细节

#### 阶段 1：爬虫（~5-10s）

```python
async def crawl(url: str) -> CrawlResult:
    # 1. 抓主页 HTML（httpx，超时 10s）
    # 2. 抓 robots.txt 解析，检查常见 AI 爬虫
    # 3. 抓 sitemap.xml（如有），最多抓 5 个子页面
    # 4. 提取：标题、meta、Schema (JSON-LD)、H1-H3、段落、链接
    # 5. 检测：发布日期、修改日期、作者署名
```

**AI 爬虫白名单**：GPTBot / ClaudeBot / anthropic-ai / Bytespider / CCBot / Google-Extended / PerplexityBot

#### 阶段 2：LLM 并行查询（~20-40s）

```python
async def query_mentions(
    brand: str,
    industry: str,
    questions: list[str],
    providers: list[str]  # ["deepseek", "kimi"]
) -> list[MentionResult]:
    # 并行：每个 provider × 每个 question 一次 LLM 调用
```

**LLM 配置**：MVP 默认启用 1 个 provider（DeepSeek，可通过 `.env` 的 `LLM_PROVIDERS` 切换或追加 Kimi）。

**Prompt 模板**：

```
请像回答用户提问一样回答："{question}"
如果答案涉及 {industry} 行业的产品/品牌/服务，
请在合适位置提到"{brand}"品牌（如果相关）。
只输出答案文本，不要额外说明。
```

**超时保护**：单次 LLM 调用 30s 超时。

#### 阶段 3：评分（~3-5s）

```python
def compute_score_card(site_audit, mentions) -> ScoreCard:
    # 五个维度各自打分（0-10）
    # 加权总分 = sum(score * weight) * 10
```

**权重配置**：

| 维度 | 权重 |
|---|---|
| authority（权威度） | 0.25 |
| relevance（内容相关性） | 0.30 |
| structure（结构化） | 0.20 |
| freshness（更新频率） | 0.15 |
| verifiability（数据可验证性） | 0.10 |

#### 阶段 4：渲染（~2-5s）

```python
def render_html(report: Report) -> str:
    # Jinja2 渲染 report.html.j2 模板

def render_pdf(report: Report, html: str) -> bytes:
    # WeasyPrint(HTML(string=html)).write_pdf()
    # 写入 data/reports/{report_id}.pdf
```

**注意**：前端 React 报告页**不依赖 Jinja2**，直接从 `/api/reports/{id}` 拿 JSON 自己渲染。Jinja2 只为 PDF 服务。

### 5.3 任务状态机

```
pending ──> crawling ──> querying_llm ──> scoring ──> rendering ──> completed
   │            │              │             │            │
   └────────────┴──────────────┴─────────────┴────┬───────┴────> failed
                                                  │
                                          pdf 失败但任务完成
                                          （pdf_available=false）
```

**特别说明**：PDF 渲染失败不导致任务失败。任务进入 `rendering` 后，HTML 报告先于 PDF 写入；只有 HTML 写入失败才让任务 `failed`。PDF 失败时任务仍 `completed`，但 `report.pdf_available=false`，前端下载按钮禁用。

### 5.4 关键不变量

| 约束 | 保证方式 |
|---|---|
| 同一时刻只有 1 个任务在跑 | asyncio.Lock；其他任务在 `pending` 状态等待，不并发执行 |
| 等待中的任务状态 | 仍为 `pending`（不进入 `crawling`），等当前任务完成才被调度 |
| 任务结果可恢复 | 每阶段更新 status + 进度到 SQLite |
| 单次诊断总时长上限 90s | 顶层 `asyncio.wait_for` |
| LLM 调用失败可重试 | 单次调用失败重试 1 次，仍失败则该问题标记 error 不计入 |

### 5.5 前端轮询策略

```typescript
useQuery({
  queryKey: ['task-status', taskId],
  queryFn: () => api.getTaskStatus(taskId),
  refetchInterval: (data) => {
    if (data?.status === 'completed' || data?.status === 'failed') return false;
    return 2000;  // 2 秒一次
  },
})
```

## 6. 输出组合

**已确认组合：应用内查看 + 后端预渲染 PDF 下载**

| 路径 | 实现 |
|---|---|
| 报告页（应用内） | React 路由 `/report/:id`，拉 JSON 自己渲染 |
| PDF 下载 | `/api/reports/:id/pdf` 后端 WeasyPrint 预渲染文件下载 |
| Jinja2 用途 | 仅 PDF 模板的 HTML 中间产物，不参与 Web SSR |
| 公开分享 URL | **不做**（MVP 不需要）|

## 7. 错误处理

### 7.1 错误分类

| 错误类型 | 示例 | 用户反馈 | 系统行为 |
|---|---|---|---|
| 输入校验错误 | URL 格式错 | 表单红色提示 | API 返回 422 |
| 任务不存在 | task_id 不存在 | "报告不存在" | 404 |
| 爬虫部分失败 | sitemap 404 | 报告标注警告 | 继续 |
| 爬虫完全失败 | DNS 失败 | "官网无法访问" | 任务 failed |
| LLM 部分失败 | 1 个问题超时 | 报告标注 | 继续，基于成功样本 |
| LLM 完全失败 | API key 错 | "AI 服务暂时不可用" | 任务 failed |
| PDF 渲染失败 | 字体缺失 | 网页可看，PDF 按钮禁用 | 任务 completed（PDF 失败不影响）|

### 7.2 错误处理层级

**层级 1：API 边界** — Pydantic 自动校验，失败 422
**层级 2：服务编排** — try/except 捕获领域异常，转任务状态
**层级 3：领域层** — 自定义异常类（`CrawlError` / `LlmError` / `ScoreError` / `RenderError`）

### 7.3 LLM 特殊处理

```python
async def query_single(provider, question, brand, industry, max_retries=1):
    for attempt in range(max_retries + 1):
        try:
            response = await asyncio.wait_for(_call_llm(...), timeout=30.0)
            return _parse_mention_result(...)
        except asyncio.TimeoutError:
            ...
        except LlmError as e:
            if not e.retryable:
                break
            ...
    # 所有重试失败 → 返回 MentionResult with error="..."
```

### 7.4 边界情况

| 情况 | 处理 |
|---|---|
| robots.txt 不存在 | 视为允许所有爬虫（warn） |
| sitemap.xml 不存在 | 只爬主页 |
| 品牌名含特殊字符 | LLM prompt 转义，regex 容错 |
| 官网是 SPA | `crawl_status=partial`，报告顶部横幅警告"该网站为单页应用，爬虫无法读取 JS 渲染后的内容，诊断结果仅供参考" |
| 目标问题含敏感词 | LLM 拒答 → 该样本 error，不计入 |
| 磁盘空间 < 100MB | 启动失败并提示 |

### 7.5 日志

```python
import structlog
logger = structlog.get_logger()

logger.info("diagnosis_started", task_id=..., brand=...)
logger.info("crawl_completed", task_id=..., status=..., duration_ms=...)
logger.info("llm_query_completed", task_id=..., question=..., provider=..., mentioned=...)
logger.info("diagnosis_completed", task_id=..., overall_score=..., duration_s=...)
logger.error("diagnosis_failed", task_id=..., stage=..., error=...)
```

MVP 日志输出 stdout，docker-compose 控制台查看。**不接 ELK / Sentry**。

## 8. 测试策略

### 8.1 测试金字塔

```
        E2E 测试 (3-5 个)
       ┌──────────────┐
       │  集成测试      │  (10-15 个)
       │  单元测试      │  (40-60 个)
```

### 8.2 单元测试

**评分引擎必须充分测试**（核心 IP）：

```python
class TestComputeScoreCard:
    def test_perfect_site_scores_high(self): ...
    def test_no_mentions_scores_zero_relevance(self): ...
    def test_partial_failures_handled(self): ...
    def test_weights_sum_to_one(self): ...
```

其他模块：`test_crawler.py` / `test_llm_client.py` / `test_renderer.py`

### 8.3 集成测试

```python
class TestDiagnosisAPI:
    async def test_submit_creates_task(self, client): ...
    async def test_submit_with_invalid_url_returns_422(self, client): ...
    async def test_get_nonexistent_task_returns_404(self, client): ...
    async def test_status_polling_workflow(self, client): ...
```

慢测试标记 `@pytest.mark.slow`，日常开发只跑单元测试。

### 8.4 E2E 测试

```typescript
// Playwright
test('完整诊断流程', async ({ page }) => {
  // 填表 → 提交 → 等待完成 → 查看报告 → 下载 PDF
});
```

**E2E 只在本地手动跑**，不强制每次提交流程跑。

### 8.5 手动验证清单（发布前必跑）

- [ ] **场景 1：完整诊断流程** — 提交真实品牌 90s 内完成，报告含雷达图和 ≥3 条建议
- [ ] **场景 2：网站无法访问** — 任务 failed，提示"官网无法访问"
- [ ] **场景 3：LLM 部分失败** — 错误 API key，mention_rate 显示 N/A
- [ ] **场景 4：PDF 下载** — PDF 文件可正常打开，中文不乱码

### 8.6 验收标准（Definition of Done）

| 指标 | 标准 |
|---|---|
| 所有单元测试通过 | ✅ |
| 所有集成测试通过 | ✅ |
| 后端覆盖率 ≥ 70%（评分引擎 ≥ 90%）| ✅ |
| 手动验证清单 4 项全过 | ✅ |
| docker-compose 一键启动成功 | ✅ |
| README 含本地启动步骤 + API key 配置 | ✅ |

## 9. 合规与边界

### 9.1 不做的事（黑帽 GEO 红线）

🚫 批量生成虚构软文
🚫 数据污染（伪造数据/排名）
🚫 代写软文冒充权威
🚫 直接付费操纵 AI 输出
🚫 抹黑竞品

### 9.2 只做的事（白帽 GEO）

✅ 让品牌的**真实信息**更结构化
✅ 评估 Schema/EEAT/结构化等可优化项
✅ 监测 AI 提及率作为基线
✅ 提供可执行的优化建议（不直接代执行）

### 9.3 免责

报告中的所有建议是基于公开 GEO 方法论的通用建议，不构成具体法律/财务/医疗建议（YMYL 场景）。

## 10. 风险与已知短板

| 风险 | 影响 | 缓解 |
|---|---|---|
| LLM API 不稳定 | 诊断失败 | 重试机制 + 部分失败容错 |
| SPA 网站爬不到 | 报告数据不全 | 明确警告用户 |
| LLM 答案不一致 | 提及率波动 | 多次采样（v0.2 考虑） |
| WeasyPrint 字体配置 | PDF 中文乱码 | Dockerfile 内嵌中文字体 |
| 单进程并发限制 | 用户需排队 | MVP 接受，v0.2 拆分 Worker |

## 11. 未来版本规划（v0.2+ 不在本设计范围）

- v0.2：内容改写助手（BLUF 重写、Schema 生成、FAQ 结构）
- v0.3：完整闭环（自动发布到 WordPress / 公众号 + 监测变化）
- v0.4：多用户系统、权限管理、历史趋势
- v0.5：竞品对比、行业基准
- v0.6：Playwright 渲染 SPA 内容
