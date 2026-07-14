# GEO2 Multi-Agent 拆分设计 spec

> 日期: 2026-07-14
> 状态: 待用户 review
> 关联文档:
> - 项目根地图 `D:\GEO2\AGENTS.md`
> - 锐评基线 `D:\GEO2\docs\review\README.md` (50/55 A+ 卓越)
> - 升级设计 `D:\GEO2\docs\superpowers\specs\2026-07-14-geo2-upgrade-design.md`
> - 简历 `D:\GEO2\docs\RESUME_GEO_Agent_v5.md` + `v5_1page.md`

---

## 1. 背景与目标

### 1.1 起点状态

GEO2 当前架构:**单 Agent (ReAct 循环) + 5 工具 + 后台异步任务链**。

- Agent Loop: `app/domain/agent/react_loop.py` (576 行,自写,无 LangGraph)
- 5 工具: `diagnose_brand` / `search_knowledge` / `list_knowledge_bases` / `generate_article` / `create_generation_task`
- 后台子域: `monitor/` (APScheduler 调 LLM 查提及率) + `publisher/` (WordPress 发布) + `generator/` (ContentWriter)
- 总分: **50/55 A+ 卓越级**,11 维度评分无短板 (4 个 5.0 + 4 个 4.5 + 2 个 4.0 + 1 个 4.0)
- 测试覆盖: 540 原有 + 200+ 新增 ≈ 740 个,pytest 全绿

### 1.2 改造动机

**两层动机**:

1. **工程动机(主)**: 流程中 `ContentWriter` 和 `MonitorService` 与主 Agent **职责错位**——它们都不需要 ReAct 状态,也不在用户对话窗口内运行,但当前用"工具调用"或"独立 worker"形式挂载,边界模糊。专业化拆分能让职责更清晰、可独立评测、可独立版本化。
2. **简历动机(辅)**: 当前简历 v5 §5 保守边界明确写"无 multi-agent / handoff 机制(README v1.0 推迟)",这是**唯一**的诚实承认短板。引入 2 个 specialist 后,可改写为"主 Agent + 2 specialist,handoff 协议 5 条工程纪律"——把减分项变加分项。

### 1.3 非目标 (Out of Scope)

- **不引入 LangGraph / LangChain / CrewAI / AutoGen 等任何外部框架**。继续自写,延续 GEO2 v0.4 起的显式架构决策(AGENTS.md §6.5)。
- **不拆 Diagnose / Search / List 三个工具**。它们仍保留为主 Agent 的工具,因为它们需要主 Agent 的上下文路由。
- **不实现"写—评—改"三 Agent 循环**。GEO2 当前的审核在前端做(人审),不引入 LLM 评审 Agent(避免成本翻倍且无明显收益)。
- **不引入 Multi-Agent 状态共享层**。Specialist 上下文严格隔离,仅通过 `HandoffRequest` / `HandoffResult` 契约通信。

---

## 2. 架构(改造前后对比)

### 2.1 改造前(当前)

```
[用户对话入口]
    ↓
[Agent / ReAct Loop / 5 工具]
    ├─ diagnose_brand      → DiagnosisService
    ├─ search_knowledge    → HybridSearch
    ├─ list_knowledge_bases
    ├─ generate_article    → ContentWriter    (写工具,后台异步)
    └─ create_generation_task → TaskWorker    (批量任务)

后台子系统(与主 Agent 无 handoff):
  MonitorService  ─ APScheduler ─→ LLM query ─→ snapshot
  PublisherService ─ 写工具完成 ─→ WordPress API
```

### 2.2 改造后

```
[用户对话入口]
    ↓
[Agent / ReAct Loop / 5 工具]                       ← 主 Agent (不变)
    ├─ diagnose_brand      → DiagnosisService
    ├─ search_knowledge    → HybridSearch
    ├─ list_knowledge_bases
    ├─ generate_article    → ContentWriterSpecialist.handoff()    ← ★ 走 handoff
    └─ create_generation_task → ContentWriterSpecialist.handoff_batch()  ← ★ 走 handoff

ContentWriterSpecialist                                ← ★ Specialist #1 (新增)
  - 上下文: 只看 (system_prompt + brand + topic + chunks),无 ReAct 状态
  - 工具: 无工具调用(纯生成)
  - 输出: 文章正文 (流式 SSE)
  - 评测: 独立 LLM-as-judge

MonitorSpecialist                                      ← ★ Specialist #2 (新增)
  - 上下文: 只看 (brand + industry + questions + providers),无 ReAct 状态
  - 工具: 无工具调用(纯查询+判定)
  - 输出: snapshot + 提及率 + 平均位置 + 阈值告警
  - 调度: APScheduler 触发(不变),但内部走 specialist 路径
```

### 2.3 关键变化点

| 变化 | 文件 | 说明 |
|---|---|---|
| **新增 handoff 协议** | `app/domain/agent/handoff.py` | 通用 `HandoffRequest` / `HandoffResult` 契约 + 5 条工程纪律 |
| **新增 handoff 持久化** | `app/repositories/handoff_log_repo.py` + ORM 表 `handoff_log` | 幂等键 + 成本归因 |
| **抽 ContentWriterSpecialist** | `app/domain/agent/content_writer_specialist.py` | 包装 `ContentWriterAgent` + `task_worker` 的写文章路径 |
| **抽 MonitorSpecialist** | `app/domain/monitor/monitor_specialist.py` | 包装 `execute_monitor_run` + APScheduler 入口 |
| **改造 tool_executor** | `app/domain/agent/tool_executor.py` | `generate_article` / `create_generation_task` 走 `ContentWriterSpecialist.handoff()` |
| **改造 monitor scheduler** | `app/domain/monitor/scheduler.py` | 触发时调 `MonitorSpecialist.run()` 而非 `execute_monitor_run` |
| **改造 settings** | `app/core/config.py` | 加 `handoff_timeout_seconds` / `handoff_max_retries` / `handoff_log_retention_days` |

---

## 3. Handoff 协议设计(核心工程纪律)

### 3.1 数据契约

**`app/domain/agent/handoff.py`** (新增, ~80 行):

```python
from dataclasses import dataclass
from datetime import datetime
from typing import Literal


@dataclass(frozen=True)
class HandoffRequest:
    """主 Agent → Specialist 的最小契约。"""

    handoff_id: str                # 幂等键,UUID4
    specialist: Literal["content_writer", "monitor"]
    task_id: str                   # 主 Agent session 内 task_id,用于日志关联
    session_id: str                # 主 Agent session_id,用于审计追溯
    started_at: datetime
    timeout_seconds: int           # 默认 300 (content_writer) / 60 (monitor)
    payload: dict                  # specialist 专属入参


@dataclass
class HandoffResult:
    """Specialist → 主 Agent 的回包。"""

    handoff_id: str
    status: Literal["success", "failed", "timeout", "cancelled"]
    result: dict | None
    error: str | None
    duration_ms: int
    token_usage: dict              # 评测与成本归因
    # 字段: prompt_tokens / completion_tokens / total_tokens
```

### 3.2 5 条工程纪律(必须全部实现)

**纪律 1: 幂等键 (`handoff_id`)** — Specialist 收到重复 `handoff_id` → 直接返回上次 `HandoffResult` (查 `handoff_log` 表),不重新执行生成。

**纪律 2: 超时 (`timeout_seconds`)** — Specialist 超时(默认 300s / 60s)→ 落 `status=timeout` → 主 Agent catch → 降级路径。

**纪律 3: 状态隔离** — Specialist 不持有主 Agent 的 ReAct 状态,只接 `payload` dict,使用独立 session (DB session / LLM client),不污染主 Agent 上下文。

**纪律 4: 失败回退** — Specialist 抛未捕获异常 → 主 Agent catch `SpecialistHandoffError` → 降级为直接调底层 service:
- ContentWriter specialist 失败 → 降级调 `ContentWriterAgent.stream_article()` (旧路径,保留兼容)
- Monitor specialist 失败 → 降级调 `MonitorService.execute_monitor_run()` (旧路径,保留兼容)

**纪律 5: 成本归因** — 每次 handoff 落 `handoff_log` 表 (specialist / handoff_id / task_id / session_id / started_at / duration_ms / token_usage / status / error),用于:
- 成本 dashboard 按 specialist 聚合
- token baseline 对比
- 失败率 / 超时率监控

### 3.3 handoff_log 表结构

```python
# app/models/orm_v05.py (新增)

class HandoffLogORM(Base):
    __tablename__ = "handoff_log"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)  # = handoff_id
    specialist: Mapped[str] = mapped_column(String(32), index=True)
    task_id: Mapped[str | None] = mapped_column(String(36), index=True, nullable=True)
    session_id: Mapped[str | None] = mapped_column(String(36), index=True, nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime, index=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(String(16), index=True)  # success/failed/timeout/cancelled
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    prompt_tokens: Mapped[int] = mapped_column(Integer, default=0)
    completion_tokens: Mapped[int] = mapped_column(Integer, default=0)
    total_tokens: Mapped[int] = mapped_column(Integer, default=0)
```

### 3.4 Settings 新增配置

```python
# app/core/config.py (新增字段)

class Settings(BaseSettings):
    # ... 已有字段

    # Handoff 协议(v0.6+ Multi-Agent 改造)
    handoff_timeout_content_writer: int = 300   # 秒
    handoff_timeout_monitor: int = 60            # 秒
    handoff_max_retries: int = 1                 # specialist 失败重试次数(不算超时)
    handoff_log_retention_days: int = 90         # handoff_log 表保留天数
    handoff_idempotency_window_hours: int = 24   # 幂等键有效期
```

---

## 4. ContentWriterSpecialist 详细设计

### 4.1 接口

```python
# app/domain/agent/content_writer_specialist.py (新增, ~150 行)

class ContentWriterSpecialist:
    """写文章 specialist。职责单一:基于 KB 召回生成单篇/批量文章。"""

    def __init__(self, settings: Settings, session_factory: async_sessionmaker):
        self.settings = settings
        self.session_factory = session_factory

    async def handoff(self, request: HandoffRequest) -> HandoffResult:
        """主 Agent 委派入口。实现 5 条工程纪律。"""

    async def handoff_batch(self, request: HandoffRequest) -> HandoffResult:
        """批量任务委派入口(对应 create_generation_task 工具)。"""

    async def _execute_with_timeout(self, payload: dict) -> dict:
        """内部实现,带 timeout。"""

    async def _check_idempotency(self, handoff_id: str) -> HandoffResult | None:
        """纪律 1: 查 handoff_log 是否有相同 handoff_id 的成功记录。"""

    async def _log_result(self, request: HandoffRequest, result: HandoffResult) -> None:
        """纪律 5: 落 handoff_log。"""
```

### 4.2 与现有代码的关系

- **不重写 `ContentWriterAgent`**(已存在,`app/domain/generator/content_writer_agent.py`)。Specialist 是它的**包装层**,负责 handoff 纪律;底层生成逻辑仍走 `ContentWriterAgent.stream_article()`。
- **不重写 `task_worker.py`**。Specialist 接管"主 Agent 写工具"的入口;`task_worker` 仍服务于 v0.2 批量任务(无主 Agent 上下文场景)。
- **保留 `_execute_generate_article_confirmed` 路径** 作为降级 fallback(v0.6 P1.6 旧 HITL 路径),纪律 4 失败回退时使用。

### 4.3 Payload schema

```python
# generate_article 工具 → ContentWriterSpecialist
{
    "mode": "single",
    "kb_id": "...",
    "brand": "...",
    "topic": "...",
    "keywords": ["..."],
    "style": "neutral|professional|casual",
    "target_length": 1500,
    "chunks": [...]  # 由主 Agent 提前 search_knowledge 召回
}

# create_generation_task 工具 → ContentWriterSpecialist
{
    "mode": "batch",
    "kb_id": "...",
    "article_count": 5,
    "style": "...",
    "target_length": 1500,
    "topics": [...]  # 可选,缺省由 specialist 自动规划
}
```

---

## 5. MonitorSpecialist 详细设计

### 5.1 接口

```python
# app/domain/monitor/monitor_specialist.py (新增, ~120 行)

class MonitorSpecialist:
    """监测 specialist。职责单一:定期查 LLM 提及率,产出 snapshot。"""

    def __init__(self, settings: Settings, session_factory: async_sessionmaker):
        self.settings = settings
        self.session_factory = session_factory

    async def run(self, monitor_task_id: str) -> HandoffResult:
        """APScheduler 触发入口。"""

    async def _execute_with_timeout(self, monitor_task_id: str) -> dict:
        """内部实现,带 timeout 60s。"""

    async def _log_result(self, request: HandoffRequest, result: HandoffResult) -> None:
        """纪律 5: 落 handoff_log(注: monitor 不走主 Agent,handoff_id 由 monitor_task_id 派生)。"""
```

### 5.2 与现有代码的关系

- **不重写 `MonitorService.execute_monitor_run`**(已存在,`app/domain/monitor/monitor_service.py`)。Specialist 是它的**包装层**。
- **APScheduler 触发点改造**:`scheduler.py` 仍触发同一定时任务,但回调从 `execute_monitor_run` 改为 `MonitorSpecialist.run`。
- **handoff_id 派生**:`f"monitor-{monitor_task_id}-{started_at.isoformat()}"`,确保同 monitor_task 同一时刻执行可幂等;同一 monitor_task 不同时刻是独立执行(避免 24h 幂等窗口吃掉正常定时任务)。

### 5.3 Payload schema

```python
# MonitorSpecialist.run 内部 payload
{
    "monitor_task_id": "...",
    "brand": "...",
    "industry": "...",
    "target_questions": ["..."],
    "providers": ["deepseek", "kimi", "..."],
}
```

---

## 6. 11 维度评分影响预估

| # | 维度 | 当前 | 改造后 | 变化 | 理由 |
|---|---|---|---|---|---|
| 01 | Agent Loop | 4.5 | 4.5 | → | 主循环不动 |
| 02 | 工具边界 | 5.0 | 4.5 | **-0.5** | 2 个工具变成 specialist handoff,工具集"不纯" |
| 03 | 上下文可控 | 5.0 | 5.0 | → | specialist 上下文更小反而更可控 |
| 04 | 权限策略 | 5.0 | 5.0 | → | handoff 不增加新权限面 |
| 05 | 失败恢复 | 5.0 | 5.0 | → | 5 条工程纪律直接服务此维度 |
| 06 | 评测体系 | 4.5 | **5.0** | **+0.5** | 2 specialist 可独立 LLM-as-judge,直接升分 |
| 07 | 可观测性 | 4.5 | **5.0** | **+0.5** | handoff_log 表 + 三出口埋点更清晰 |
| 08 | HITL | 4.5 | 4.5 | → | 不变 |
| 09 | 成本/延迟 | 5.0 | 4.5 | **-0.5** | handoff 本身有 50-100ms 开销 + handoff_log 写入 |
| 10 | 架构分层 | 4.0 | 4.0 | → | specialist 在 domain/agent/ + domain/monitor/ 下,符合分层 |
| 11 | Harness 范式 | 4.5 | 4.5 | → | 不变 |
| **总分** | | **50.0** | **50.0** | **→** | **持平**(2 升 2 降 7 不变) |

**关键门槛**: 总分必须 ≥ 50.0(卓越级)。如果实施过程中某个维度评分实测低于预期,需要补强(例如 02 工具边界若降到 4.0 以下,需要同步加 `tool_executor` 显式声明 specialist 委派路径,让工具边界重新清晰)。

---

## 7. 实施拆分(3 个 sprint,总 4-6 天)

### Sprint 1: Handoff 协议骨架(1d)

- `app/domain/agent/handoff.py` — `HandoffRequest` / `HandoffResult` dataclass
- `app/models/orm_v05.py` — `HandoffLogORM` + DB 迁移脚本
- `app/repositories/handoff_log_repo.py` — 幂等键查询 + 日志写入
- `app/core/config.py` — 4 个新 settings 字段
- 测试: `tests/test_handoff.py` — 5 条纪律各 1 个测试,共 5 个
- commit: `feat(agent): handoff 协议骨架 + 5 条工程纪律`

### Sprint 2: ContentWriterSpecialist(2d)

- `app/domain/agent/content_writer_specialist.py` — 包装 ContentWriterAgent
- `app/domain/agent/tool_executor.py` — `generate_article` / `create_generation_task` 改走 specialist
- 测试: `tests/test_content_writer_specialist.py` — 8-10 个测试
- 保留旧 `_execute_generate_article_confirmed` 路径(降级 fallback)
- 集成测试: `tests/test_integration_generate_via_specialist.py`
- commit: `feat(agent): ContentWriterSpecialist + tool_executor 委派改造`

### Sprint 3: MonitorSpecialist + 评测 + 文档(1-2d)

- `app/domain/monitor/monitor_specialist.py` — 包装 execute_monitor_run
- `app/domain/monitor/scheduler.py` — 触发路径改造
- `backend/evals/content_writer_judge.py` — LLM-as-judge 评测(对应 06 升 5.0)
- 测试: `tests/test_monitor_specialist.py` — 5 个测试
- 评测基线: `backend/evals/baseline_report.md` 复跑,新增 specialist 列
- commit:
  - `feat(monitor): MonitorSpecialist specialist 化`
  - `feat(eval): LLM-as-judge 评测覆盖 2 specialist`

### Sprint 4(可选): 简历升级(0.5d)

- `docs/RESUME_GEO_Agent_v5.md` §1.4 ① 任务边界 — 改写 multi-agent 段
- `docs/RESUME_GEO_Agent_v5.md` §2.5 Q13-Q15 — 重写答案(从"没拆"改为"拆 2 个")
- `docs/RESUME_GEO_Agent_v5_1page.md` — 技能清单 + 项目经历
- `docs/RESUME_GEO_Agent_v5.md` §5 保守边界 — 删除"无 multi-agent"条
- `docs/review/README.md` 11 维度评分表 — 更新
- commit: `docs(resume): multi-agent 改造后简历升级`

---

## 8. 验收门

### 8.1 工程验收(必须全部通过)

- [ ] 2 个 specialist 实现完成 (`content_writer_specialist.py` + `monitor_specialist.py`)
- [ ] Handoff 协议 5 条工程纪律全部实现 + 测试覆盖
- [ ] `handoff_log` 表 DB 迁移成功 + 索引建立
- [ ] 所有原有测试不破坏(回归保护)
- [ ] 新增 18-20 个测试全部通过
- [ ] `pytest backend/tests/` 全绿
- [ ] `ruff check` 通过
- [ ] 11 维度评分**总分 50.0 不变**(允许 2 维度 ±0.5 浮动,但总分必须 ≥ 50.0)

### 8.2 简历验收

- [ ] `v5_1page.md` 关键词 "Multi-Agent" / "Specialist" / "Handoff" 出现 ≥ 5 次
- [ ] `v5.md` §2.5 Q13-Q15 三题答案改写完成
- [ ] `v5.md` §5 保守边界 删除"无 multi-agent"条目
- [ ] 简历 PDF 投递版格式正确(占位符全部替换)

### 8.3 文档验收

- [ ] `docs/review/README.md` 11 维度评分表已更新
- [ ] `docs/review/99-improvement-plan.md` 标记本改造为 P2 卓越化已实现
- [ ] `docs/UPGRADE_SUMMARY.md`(若存在)新增本改造章节

---

## 9. 风险与缓解

| # | 风险 | 概率 | 影响 | 缓解 |
|---|---|---|---|---|
| 1 | Handoff 协议复杂度过高,引入 bug | 中 | 高 | 5 条纪律对应 5 个独立测试;先写 test_handoff.py 再写实现(TDD) |
| 2 | ContentWriter 当前是同步调用,specialist 化后前端流式路径要改 | 高 | 中 | 保留旧 `_execute_generate_article_confirmed` 路径做 fallback,加 feature flag `handoff_enabled` |
| 3 | 评测体系 4.5 → 5.0 需真做 LLM-as-judge,工时可能超 | 中 | 中 | Sprint 3 同步建 `content_writer_judge.py`,跑通 30 条样例即可(无需 200 条) |
| 4 | 11 维度评分降级不可接受 | 中 | 高 | 02 + 09 各降 0.5 是预期;若实测 < 4.0,需要补强 tool_executor 显式声明委派路径 |
| 5 | Handoff log 表可能膨胀,影响 DB 性能 | 低 | 中 | `handoff_log_retention_days=90` + 定时清理任务(放入 backlog) |
| 6 | Specialist 失败时降级到旧路径,可能行为不一致 | 中 | 中 | 降级路径与 specialist 路径做 A/B 比对测试,确保输出 byte-level 相同 |

---

## 10. 设计依据(为什么这么设计)

### 10.1 对照 InkOS 的 4 个项目调研结论

`LangGraph / AutoGen / CrewAI / MetaGPT` 4 个项目的共性"什么时候该拆"判断标准:

| 标准 | GEO2 满足? |
|---|---|
| ① 职责/上下文不可兼得 | ⚠️ 部分(ContentWriter / Monitor 边界错位) |
| ② 写—评—改/Plan-Execute-Critique 对抗迭代 | ❌ 不满足(审核在前端做) |
| ③ 可独立物化的中间制品 | ❌ 不满足(文章是终态制品,无中间制品) |
| ④ 需要多种控制流(顺序/分支/循环/人在环) | ❌ 不满足(单 ReAct 循环 + HITL 已够) |
| ⑤ 需要动态路由(Manager 委派) | ❌ 不满足(LLM 自由选工具已是动态) |
| ⑥ 角色工具/权限/上下文差异巨大 | ✅ 满足(ContentWriter 无工具 / Monitor 无对话) |
| ⑦ 可并行子任务 | ❌ 不满足(顺序决策) |
| ⑧ 组织/业务语义映射 | ❌ 不满足(业务流程已是 Agent + 工具) |

**结论**: 8 条标准中仅 ① 部分 + ⑥ 满足,因此**只拆 2 个 specialist**(标准 ⑥ 的直接体现),不引入 ④ ⑤ ⑦ 等更重的多 Agent 机制(标准不满足,引入是负优化)。

### 10.2 对照 GEO2 5 工具的拆 Agent 决策

| 工具 | 拆 / 不拆 | 理由 |
|---|---|---|
| `diagnose_brand` | 不拆 | 需要主 Agent 路由决策(诊断什么品牌/什么维度),不能脱离对话 |
| `search_knowledge` | 不拆 | 召回结果需要主 Agent 二次判断(够不够 / 要不要重召) |
| `list_knowledge_bases` | 不拆 | 元信息查询,体量小,没必要拆 |
| `generate_article` | **拆** | 职责单一(写文章),无工具调用,无 ReAct 状态 |
| `create_generation_task` | **拆** | 与 generate_article 同链路,共享 specialist |
| (后台)Monitor | **拆** | 无对话入口,纯查询+判定,与主 Agent 边界清晰 |

---

## 11. 后续路线(本 spec 不包含,仅备查)

- v0.7 候选: DiagnoseAgent(独立 diagnostic 流程) — 但当前 5 工具规模不迫切
- v0.7 候选: HITL 多场景(决策 / 补充输入 / 进度确认)— 在 P1 升级路线已立项
- v1.0 候选: Multi-user / 权限隔离 / 跨 session 学习 — README v1.0 路线
- v1.0 候选: handoff_log 自动清理任务(防止表膨胀)

---

## 12. 变更记录

| 日期 | 版本 | 变更 | 作者 |
|---|---|---|---|
| 2026-07-14 | v0.1 草案 | 初版,基于 brainstorming 5.1-5.7 方案展开 | Claude |
| TBD | v0.2 | 用户 review 后修订 | TBD |
| TBD | v1.0 | 实施完成 + 验收通过 | TBD |
