# GEO2 技术债追踪表

> 启动日期：2026-07-14（阶段 2 P1#22 / Task 23）
> 关联：锐评 [11-harness-engineering.md](./review/11-harness-engineering.md) §3.6

---

## 元数据约定

| 字段 | 含义 |
| --- | --- |
| **ID** | `TD-XXX` 唯一编号 |
| **优先级** | P0（阻塞）/ P1（重要）/ P2（可选） |
| **来源** | 锐评维度 / 阶段 X / 自发现 |
| **状态** | 🟢 已处理 / 🟡 处理中 / 🔴 未处理 |
| **估时** | 预估修复成本 |

---

## 阶段 2 启动时首批登记项

### TD-001: domain → services 反向依赖（3 处违反 import-linter）
- **来源**：[import-linter 配置](./backend/.import-linter.toml) 阶段 2 P1#21（Task 22）
- **优先级**：P1（架构整洁度，不阻塞功能）
- **状态**：🔴 未处理
- **估时**：1-2d
- **违反清单**：
  - `app/domain/agent/tool_executor.py:93` → `app.services.diagnosis_service.DiagnosisService`
  - `app/domain/agent/tool_executor.py:218, 248` → `app.services.hybrid_search`
  - `app/domain/agent/memory.py:33` → `app.services.embedding.EmbeddingService`
- **修复方向**：
  1. 方案 A：把上述 services 调用上移到 api/tool_executor 调用方（保持纯 DI）
  2. 方案 B：在 domain 抽象 Protocol 接口，services 实现接口，domain 依赖 Protocol（不在同包）
- **阻塞 linter 契约**：API depends on Services/Domain/Repos/Models + Services depends on Domain/Repos/Models
- **影响范围**：domain 层所有测试需重跑，tool_executor 行为契约不变

### TD-002: P2 待办项（25 项熵管理 / 自适应模型 / 用户偏好学习）
- **来源**：[99-improvement-plan.md §低优先级](./review/99-improvement-plan.md)
- **优先级**：P2（可选）
- **状态**：🔴 未处理
- **估时**：~55d
- **子项**：
  - TD-002.1 自适应模型选择（5d）
  - TD-002.2 用户偏好学习（3d）
  - TD-002.3 月度成本 dashboard（3d）
  - TD-002.4 ORM 迁移脚本（5d）
  - TD-002.5 API 层加 auth（2d）
  - TD-002.6 定期后台 agent 扫描代码偏差（5d）
  - TD-002.7 自动重构 PR 流程（5d）
  - ...（其余见 99）
- **修复方向**：阶段 4（卓越化）按需挑做

### TD-003: mypy strict 模式初次启用会暴露大量历史错误
- **来源**：阶段 2 P1 风险预案（锐评 11-harness）
- **优先级**：P2（harness 完善度）
- **状态**：🔴 未处理（当前 mypy 仍 `|| true` 容错）
- **估时**：3-5d（分批修复）
- **修复方向**：
  1. 先开启 mypy 检查新代码（加 `disallow_untyped_defs` 仅对 `app/core/` 新文件）
  2. 分批修旧模块，加 `# type: ignore[xxx]` 标注
  3. 最终全栈 strict 模式

### TD-004: baseline_report.md pass rate 56.7%（mock 阶段）
- **来源**：[backend/evals/baseline_report.md](./backend/evals/baseline_report.md)
- **优先级**：P1（评测可信度）
- **状态**：🔴 未处理（mock agent，boundary 类 0%）
- **估时**：1d
- **修复方向**：
  1. 接入真实 AgentService.run_agent_turn（替换 `_mock_agent_response`）
  2. 配置 OPENAI_API_KEY 后 `judge._llm_score` 自动启用
  3. baseline 重跑预期 pass rate 显著提升
- **关联**：阶段 2 门控验证项之一

### TD-005: 端到端 turn 延迟 P95 告警阈值未配置
- **来源**：[锐评 09-cost-latency.md §3.7](./review/09-cost-latency.md)
- **优先级**：P2
- **状态**：🟡 处理中（Task 25 实现慢查询告警，turn 延迟告警需后续）
- **估时**：0.5d
- **修复方向**：复用 Task 25 的 LLM > 60s 告警模式，加 P95 turn 延迟监控

### TD-006: HITL 覆盖度窄（仅 generate_article 暂停）
- **来源**：[锐评 08-hitl.md §3.4](./review/08-hitl.md)
- **优先级**：P2
- **状态**：🔴 未处理
- **估时**：5d（多类 HITL 事件）
- **修复方向**：
  - 决策类（approve/reject 已实现）
  - 补充输入类（用户补充参数）
  - 进度确认类（long-running task 中途确认）
- **关联**：Task 14 声明式权限扩展点

### TD-007: Prometheus 指标导出
- **来源**：[锐评 07-observability.md §3.5](./review/07-observability.md)
- **优先级**：P2
- **状态**：🔴 未处理
- **估时**：2d
- **修复方向**：`/metrics` 端点暴露 prometheus_client 格式指标，结构化日志已有数据可映射

### TD-008: 评测集与 CI 集成
- **来源**：[锐评 06-evaluation.md §3.4](./review/06-evaluation.md)
- **优先级**：P2
- **状态**：🔴 未处理（当前 evals/ 仅本地跑）
- **估时**：1d
- **修复方向**：GitHub Actions 加 evals runner 步骤，缺 OPENAI_API_KEY 时 skip

### TD-009: Fallback 模型策略（多 provider 自动切换）
- **来源**：[锐评 09-cost-latency.md §3.6](./review/09-cost-latency.md)
- **优先级**：P2
- **状态**：🔴 未处理
- **估时**：3d
- **修复方向**：复用 Task 21 `resolve_providers`，LLMClient 失败时自动切下一个 provider

### TD-010: 数据库 ORM 版本迁移脚本（v04 → 后续）
- **来源**：[锐评 10-architecture-layering.md §3.5](./review/10-architecture-layering.md)
- **优先级**：P2
- **状态**：🔴 未处理
- **估时**：5d
- **修复方向**：orm_v01-v04 历史保留，逐步整合到单一 ORM（Alembic 迁移）

---

## 汇总

| 优先级 | 总数 | 已处理 | 处理中 | 未处理 |
| --- | --- | --- | --- | --- |
| P0 | 0 | 0 | 0 | 0 |
| P1 | 2 | 0 | 0 | 2 |
| P2 | 8 | 0 | 1 | 7 |
| **合计** | **10** | **0** | **1** | **9** |

阶段 2 完成时预期关闭 TD-001（架构契约闭环）+ TD-004（baseline 重跑）。其余按阶段 3/4 推进。

---

## 添加新条目

新发现的 tech debt 在 PR 描述里引用 `TD-XXX` 编号，在本表登记并更新汇总计数。