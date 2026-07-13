# GEO2 全面升级 — 设计 Spec

| 项目 | 值 |
| --- | --- |
| 日期 | 2026-07-14 |
| 状态 | 设计完成，待用户审阅 |
| 来源 | 紧接 11 维度锐评完成（35/55 B 级） |
| 目标 | 总分 35 → 47.5+/55（A 级），覆盖 P0 + P1 + P2 |

---

## 1. 背景与目的

### 1.1 起点

刚刚完成 GEO2 11 维度质量锐评，结论是 **35/55 B 级**（[README.md](../../review/README.md)）。11 维度评分如下：

| 维度 | 当前分 | 主要短板 |
| --- | --- | --- |
| 01 Agent Loop | 4/5 | 缺可视化与 replay |
| 02 工具边界 | 4/5 | generate_article schema drift |
| 03 上下文可控 | 4/5 | 字符截断欠 token 精度 |
| 04 权限策略 | 4/5 | 缺声明式策略 |
| 05 失败恢复 | 4/5 | 重试次数偏少 |
| **06 评测体系** | **1/5** | **重大缺失：无 evals/** |
| 07 可观测性 | 3/5 | 缺 Sentry/Langfuse |
| 08 HITL | 3/5 | 覆盖度窄 |
| 09 成本/延迟 | 3/5 | 缺端到端延迟 |
| 10 架构分层 | 3/5 | knowledge_repo 反向依赖 |
| **11 Harness 范式** | **2/5** | **缺 AGENTS.md + CI + lint** |

详细改进项见 [`docs/review/99-improvement-plan.md`](../../review/99-improvement-plan.md)（55 项 P0/P1/P2 改进清单）。

### 1.2 用户决策（已确认）

- **升级范围**：全 4 阶段（P0 + P1 + P2 都做，约 92d）
- **验收节奏**：阶段 2 后验收（一次性 review 阶段 0+1+2 产出）
- **执行隔离**：main 直接（每阶段打 tag 方便回滚）

### 1.3 目标

完成 P0 + P1（共 30 项）后预期总分 ≥ 47.5（A 级下限）；完成 P2 后达卓越级。

---

## 2. 范围与非目标

### 2.1 范围

- 实施 99-improvement-plan.md 中的 **全部 55 项**改进
- 新建配套基础设施：AGENTS.md / CI / evals/ / tech-debt-tracker.md
- TDD 优先：每个改进项先写测试再写实现
- 阶段门控：每阶段完成必跑 pytest + ruff + evals

### 2.2 非目标

- **不引入新框架**（不引 LangGraph / LangChain）
- **不重写**已有模块（最小侵入式重构）
- **不改 ORM 版本结构**（orm_v02-v04 演进历史保留）
- **不改变业务逻辑**（仅工程化补强）

---

## 3. 升级路线图（4 阶段）

### 阶段 0：基线建立（1d）

| 项 | 内容 |
| --- | --- |
| 任务 | 建 eval 基线（用当前 LLM 输出 30 条 case，记 pass rate 起点） |
| 产出 | `backend/evals/baseline_report.md` |
| 门控 | 基线数据可用于后续比较 |

### 阶段 1：P0 突击（6-8d）

| # | 改进项 | 估时 |
| --- | --- | --- |
| 1 | 建 evals/ 目录 + 30 条评测集 + LLM-as-judge | 2d |
| 2 | 建 AGENTS.md + ruff + GitHub Actions CI | 1-2d |
| 3 | 修复 knowledge_repo 反向依赖 | 0.5d |
| 4 | 同步 generate_article schema 与 v0.6 行为 | 0.5d |
| 5 | max_retries ≥3 + 指数退避 | 0.5d |
| 6 | memory.py 宽泛捕获收敛到 _LLM_TRANSIENT_EXCEPTIONS | 1d |

**阶段 1 完成后预期**：

- 总分：35 → 40
- 新增 CI / AGENTS.md / evals/
- 评测集 + 编程错误可见性提升

**门控**：

- [ ] evals/ 30 条用例可跑通 baseline
- [ ] GitHub Actions CI 通过（pytest + ruff）
- [ ] `pytest backend/tests/` 全部通过
- [ ] 验证 knowledge_repo 不再依赖 services/hybrid_search

### 阶段 2：P1 核心（20d）

12 项核心 P1（最高 ROI）：

| # | 改进项 | 估时 |
| --- | --- | --- |
| 7 | MAX_REACT_ITERATIONS → Settings | 0.5d |
| 8 | 提取嵌套 `async with factory() as session` 为 DI | 1d |
| 9 | LLM 调用失败显式降级 | 1d |
| 10 | 工具 schema description 防 drift 测试 | 0.5d |
| 11 | token 级截断（接 tiktoken） | 1d |
| 12 | 历史摘要策略（窗口+摘要双层） | 2d |
| 13 | 声明式权限策略（per-tool `requires_confirmation`） | 1d |
| 14 | HumanConfirmation 专项测试 | 1d |
| 15 | react_loop 工具失败 transient/programming 区分 | 1d |
| 16 | 故障注入测试套件 | 2d |
| 17 | 接入 Sentry | 0.5d |
| 18 | 接入 Langfuse | 0.5d |
| 19 | trace_id 串联（contextvars） | 1d |
| 20 | 显式 Providers 抽象 | 3d |
| 21 | import-linter（机械阻断分层违反） | 1d |
| 22 | tech-debt-tracker.md | 0.5d |
| 23 | 端到端 turn 延迟 + LLM 耗时 + cost 字段 | 1.5d |
| 24 | 慢查询告警（LLM > 60s） | 0.5d |
| 25 | pending 超时自动取消（5 分钟） | 0.5d |
| 26 | reject 理由进入 LLM 上下文 | 1d |

**阶段 2 完成后预期**：

- 总分：40 → 47.5（A 级下限）
- 11 维度全部 4-5 分
- 全链路可观测（trace_id + Sentry + Langfuse）

**门控**：

- [ ] 11 维度评分表 7/11 提升到 4.5+
- [ ] 540 测试通过 + 新增 ~100 测试
- [ ] import-linter 阻断测试通过
- [ ] Sentry/Langfuse 接通并显示事件
- [ ] 端到端 turn P95 < 60s 告警正常

### 阶段 3：P1 剩余（10d）

8 项 P1 次重要：

| # | 改进项 | 估时 |
| --- | --- | --- |
| 27-30 | 评测集与 CI 集成 + 人评抽样 + 评测可视化 | 3.5d |
| 31-34 | Prometheus 导出 + HITL 多场景 + 端到端测试 + 多类 HITL | 6.5d |

**阶段 3 完成后预期**：47.5 → 49（A 级中段）

### 阶段 4：P2 卓越化（55d，可选）

25 项 P2（熵管理 / 自适应模型 / 用户偏好学习 / ORM 迁移 / 自动重构 PR 等）。可按需挑做。

---

## 4. 关键文件清单

### 4.1 高频改动

- `backend/app/domain/agent/react_loop.py` — Agent Loop 核心（576 行，阶段 1/2 多处改）
- `backend/app/domain/agent/memory.py` — 记忆服务（391 行，阶段 1 收敛 8 处捕获）
- `backend/app/domain/llm_client.py` — LLM 客户端（374 行，阶段 1/2 多次改）
- `backend/app/domain/agent/tools.py` — 工具 schema（321 行，阶段 1 改 description + 阶段 2 声明式权限）
- `backend/app/repositories/knowledge_repo.py` — 知识库 repo（阶段 1 修复反向依赖）

### 4.2 新建文件

| 文件 | 阶段 | 用途 |
| --- | --- | --- |
| `AGENTS.md` | 1 | 仓库地图（~100 行） |
| `.github/workflows/ci.yml` | 1 | GitHub Actions CI |
| `backend/evals/judge.py` | 1 | LLM-as-judge 评测脚本 |
| `backend/evals/cases.py` | 1 | 30 条评测用例数据 |
| `backend/evals/runner.py` | 1 | 评测运行入口 |
| `backend/evals/baseline_report.md` | 0 | 基线数据 |
| `backend/app/core/tracing.py` | 2 | trace_id contextvars |
| `backend/app/core/providers.py` | 2 | auth/telemetry/feature flag |
| `backend/app/domain/agent/summarizer.py` | 2 | 历史摘要策略 |
| `backend/tests/test_tool_schema_drift.py` | 2 | schema 防 drift 测试 |
| `backend/tests/test_human_confirmation.py` | 2 | HumanConfirmation 专项测试 |
| `backend/tests/test_fault_injection.py` | 2 | 故障注入测试套件 |
| `docs/tech-debt-tracker.md` | 2 | 技术债追踪 |

### 4.3 修改文件

| 文件 | 阶段 | 改动 |
| --- | --- | --- |
| `backend/pyproject.toml` | 1, 2 | 新增 [tool.ruff] / [tool.mypy] / import-linter 配置 |
| `backend/requirements.txt` | 1, 2 | 新增 ruff/mypy/tiktoken/sentry-sdk/langfuse |
| `backend/app/repositories/knowledge_repo.py` | 1 | 修复反向依赖（line 262-279） |
| `backend/app/domain/agent/tools.py` | 1, 2 | 同步 schema + 声明式权限 |
| `backend/app/domain/agent/memory.py` | 1 | 收敛 8 处 except Exception |
| `backend/app/domain/llm_client.py` | 1, 2 | max_retries + 指数退避 + 慢查询告警 |
| `backend/app/domain/agent/react_loop.py` | 1, 2 | MAX_ITER → Settings + LLM 降级 + turn 延迟 |
| `backend/app/api/agent_chat.py` | 2 | reject 理由进入上下文 |
| `backend/app/main.py` | 2 | Sentry 接入 |
| `backend/app/repositories/agent_repo.py` | 2 | pending 超时支持 |

---

## 5. 复用现有代码（避免重复造轮子）

| 现有代码 | 位置 | 复用方式 |
| --- | --- | --- |
| `_LLM_TRANSIENT_EXCEPTIONS` | `content_writer.py:18-24` | 阶段 1 上移到 `exceptions.py` 共享给 memory.py |
| `react_loop._emit_metrics` | `react_loop.py:258-269` | 阶段 2 加 turn_duration_ms 字段 |
| `structlog.get_logger()` | 各模块 | 阶段 2 trace_id 通过 contextvars 注入 |
| `AgentRepository.create_message` | `agent_repo.py` | 阶段 2 pending 超时加调度任务 |
| `react_loop._drive_react_loop` | `react_loop.py:277` | 阶段 2 重构共享循环体（不破坏两入口） |

---

## 6. 实施原则

### 6.1 TDD 优先

每个改进项必须先写测试再写实现。P0 阶段的测试覆盖现状（来自 Explore 报告）：

| P0 项 | 当前覆盖 | 实施要求 |
| --- | --- | --- |
| Task 5 max_retries + 指数退避 | **缺失** | 先写 `test_query_single_retries_with_backoff` |
| Task 4 schema drift | 部分 | 加 `test_generate_article_schema_description` 断言关键行为词 |
| Task 3 反向依赖 | 部分 | 加 import-linter 阻断测试 |
| Task 6 memory.py 收敛 | 部分 | 加 transient/programming 分类测试 |

### 6.2 每项独立 commit

按"一个改进项 = 一个 commit"原则，便于审查与回滚。

### 6.3 阶段门控硬执行

每阶段完成后必须：

- 运行 `pytest backend/tests/` 全通过
- 跑 `evals/runner.py` 对比基线（如已有）
- 更新 `docs/review/README.md` 11 维度评分表
- 用户验收（阶段 2 后）

### 6.4 风险预案

| 风险 | 预案 |
| --- | --- |
| Task 5 指数退避影响总耗时 | `llm_call_timeout_s` 配合调整（30s → 45s） |
| Task 6 memory.py 收敛暴露被吞 bug | 先用 `--collect-only` 跑测试看失败，再决定保留部分宽泛捕获 |
| Task 3 反向依赖调用方迁移 | 用 git grep `search_chunks_hybrid` 全量找调用点 |
| CI 中 LLM-as-judge 缺 OPENAI_API_KEY | 设为可选步骤（缺 secret 时 skip） |

---

## 7. 验收标准

完成标准：

- [ ] 55 项改进全部实施（含 P0 6 + P1 24 + P2 25）
- [ ] 每项有独立 commit
- [ ] 每阶段有 tag（`upgrade-stage-0/1/2/3/4`）
- [ ] 总分 ≥ 47.5（阶段 2 完成后）
- [ ] 总分 ≥ 49（阶段 3 完成后）
- [ ] 总分 ≥ 50（阶段 4 完成后）
- [ ] pytest 全部通过（含新增测试）
- [ ] ruff / mypy 通过
- [ ] GitHub Actions CI 全绿
- [ ] 用户在阶段 2 后验收签字

---

## 8. 风险与开放问题

### 8.1 风险

- **GitHub Actions CI Secret 缺失**：用户需在 remote 配置 `OPENAI_API_KEY` / `LANGFUSE_PUBLIC_KEY` 等
- **mypy 初次运行可能大量报错**：需分批修复或加 `# type: ignore`
- **指数退避 + 重试**叠加可能使最坏耗时超 60s：需配合告警阈值

### 8.2 开放问题

- 阶段 4（P2 卓越化）是否全做（55d）？用户已确认全做
- evals/ 评测用例来源（手工编写 vs LLM 生成 vs 真实日志抽样）？默认手工 + 真实日志抽样
- 评测集是否含 v0.6 P1.6+ 默认走后台的 generate_article 用例？默认是

---

## 9. 文档关联

| 文档 | 关系 |
| --- | --- |
| [锐评主页](../../review/README.md) | 本计划的起点（35/55 B 级） |
| [锐评 99 改进清单](../../review/99-improvement-plan.md) | 本计划的输入（55 项） |
| [2026-07-14-geo2-quality-review-design.md](2026-07-14-geo2-quality-review-design.md) | 锐评的 spec |
| [2026-07-14-geo2-quality-review-plan.md](../plans/2026-07-14-geo2-quality-review-plan.md) | 锐评的 plan（已完成） |
| [2026-07-14-geo2-upgrade-plan.md](../plans/2026-07-14-geo2-upgrade-plan.md) | 本 spec 对应的实施 plan |
| [C:\Users\p'q'y\.claude\plans\shiny-imagining-widget.md](../../../../../Users/p'q'y/.claude/plans/shiny-imagining-widget.md) | ExitPlanMode 保存的本地 plan 文件 |

---

## 10. 给后续会话的无缝衔接说明

> 如果你是在新会话读到这份 spec，应该按以下顺序继续：

1. **读本 spec**（你已经读了）
2. **读配套 plan**：`docs/superpowers/plans/2026-07-14-geo2-upgrade-plan.md`
3. **读锐评主页**：`docs/review/README.md`（了解 35/55 B 级的起点）
4. **读 99 改进清单**：`docs/review/99-improvement-plan.md`（55 项详细描述）
5. **确认用户决策**：
   - 升级范围：全 4 阶段（已确认）
   - 验收节奏：阶段 2 后（已确认）
   - 执行隔离：main 直接（已确认）
6. **从阶段 0 开始执行**：先建 eval 基线，再做 P0 6 项
7. **每项独立 commit**：commit message 格式参考之前的锐评 commit