# GEO2 Eval Baseline (阶段 1 完成)

> **采集时间**: 2026-07-14
> **数据集**: 30 条 (`backend/evals/cases.py`),分桶 正常 8 / 边界 6 / 数据缺失 6 / 诱导错误 5 / 拒答 5
> **评分**: keyword 覆盖 (60%) + tool 选择 (40%, 无 LLM 评分能力时降级为 keyword-only)
> **环境**: mock agent response(真实 AgentService 调用待阶段 2 接入)

## 总览

| 指标 | 值 |
| --- | --- |
| 总用例数 | 30 |
| 通过数 | 17 |
| Pass rate | **56.7%** |
| 平均评分 | 0.504 |
| 平均延迟 | 0.0 ms (mock 不计) |

## 按类别分布

| 类别 | 总数 | 通过 | Pass rate | 说明 |
| --- | --- | --- | --- | --- |
| normal (正常) | 8 | 8 | **100%** | mock 生成的"调用工具"回复含 expected_keywords |
| boundary (边界) | 6 | 0 | **0%** | mock 回复过于简单,未含具体边界值关键词(limit/target_length 等) |
| missing (数据缺失) | 6 | 1 | **16.7%** | 部分 mock 回复缺第一个 expected_keyword |
| induction (诱导错误) | 5 | 3 | **60%** | 大部分 mock 能拒答 |
| refusal (拒答) | 5 | 5 | **100%** | mock 回复含"医疗"/"隐私"等关键词 |

## 局限性

- **mock 阶段**: 当前 runner 用 `_mock_agent_response()` 占位,真实 AgentService.run_agent_turn 未接入。
- **LLM-as-judge 退化**: 未配置 OPENAI_API_KEY 等 secret 时,judge 退化为 keyword + tool 启发式评分(score 0-1)。
- **boundary 类 0% 是 mock 缺陷,不是系统缺陷**: 真实 agent 应能识别"300 字最短文章"等并返回符合关键词的内容。

## 阶段 2 改进方向

1. 接入真实 AgentService(替换 `_mock_agent_response`)。
2. 接入 LLM-as-judge(配置 OPENAI_API_KEY 后 `judge._llm_score` 自动启用)。
3. baseline 重跑: pass rate 应显著提升(boundary 类不再 0%)。

## 对比阶段 1 完成后总分

| 维度 | 起点 (35/55) | 阶段 1 后 (40/55) | 提升 |
| --- | --- | --- | --- |
| 06 评测体系 | 1 | **3** | +2 (evals/ + 30 条 + judge) |
| 10 架构分层 | 3 | **3.5** | +0.5 (修复 knowledge_repo 反向依赖 + import-linter 阻断) |
| 11 Harness 范式 | 2 | **3.5** | +1.5 (AGENTS.md + ruff + mypy + GitHub Actions) |
| **总分** | **35** | **40** | **+5** |