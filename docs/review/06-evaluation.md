# 06. 评测体系

> 面试官视角：本维度在 GEO2 的现状、评分、讲述建议、改进路径。

## 1. 维度定义

自动化评测 Agent 输出质量的能力。包括：评测用例数量、场景覆盖度、失败原因分类、可回归性、CI 集成、人评结合。

依据：[`00-learning-summary.md` §6.6 / §7](./00-learning-summary.md)

## 2. 评分标准（0-5 分制）

| 分数 | 含义 | 触发条件 |
| --- | --- | --- |
| 0 | 缺失 | 无任何评测 |
| 1 | 雏形 | 仅有指标埋点 |
| 2 | 基础 | 有少量单元测试覆盖关键路径 |
| 3 | 达标 | ≥30 条评测用例、覆盖 5 类场景 |
| 4 | 良好 | 失败原因分类、可回归 |
| 5 | 卓越 | 与 CI 集成、人评结合 |

## 3. GEO2 现状调研

### 3.1 没有专门的评测体系（⚠️ 重大发现）

来源：[`backend/` 目录结构](./../backend/)

```
backend/
├── app/
├── data/
├── scripts/
├── tests/    ← 只有单元测试，无评测
├── Dockerfile
├── pyproject.toml
└── requirements.txt
```

**关键缺失**：

- ✗ 无 `evals/` 目录
- ✗ 无 `benchmarks/` 目录
- ✗ 无 golden dataset / ground truth
- ✗ 无 LLM-as-judge 评测脚本
- ✗ 无 quality scoring
- ✗ 无回归测试集

**说明**：学习路线 §7 明确要求 30-50 条覆盖 5 类场景的评测集（正常 15 / 边界 8 / 数据缺失 8 / 诱导错误 8 / 拒答 5）。GEO2 完全没有。

### 3.2 现有测试资产

来源：[`backend/tests/`](./../backend/tests/)

| 测试文件 | 覆盖 |
| --- | --- |
| `test_agent_tools.py` | 工具定义、schema、校验 |
| `test_agent_repo.py` | AgentRepository 持久化 |
| `test_agent_tool_executor_*.py` | 工具执行（create/list/search） |
| `test_agent_prompt_strategy.py` | System prompt 策略 |
| `test_api_agent_chat.py` | agent_chat API |
| `test_api_agent_sessions.py` | 会话 API |
| `test_api_knowledge*.py` | 知识库 API |
| `test_llm_chat_with_tools.py` | LLM + tools 协议 |
| `test_react_loop_metrics.py` | 指标埋点（Phase 1） |
| `test_tool_executor.py` | ToolExecutor 整体 |

**单元测试覆盖度评价**：中等 —— 覆盖了关键模块，但缺少：

- ✗ 端到端 turn 级评测（输入 → 多轮 → 输出断言）
- ✗ LLM 输出质量评测（答案是否准确、完整、无幻觉）
- ✗ 5 类场景的系统性覆盖（正常 / 边界 / 数据缺失 / 诱导错误 / 拒答）

### 3.3 指标埋点（雏形）

来源：[`react_loop.py` L238–L269](./../backend/app/domain/agent/react_loop.py)

```python
def _new_metrics() -> dict:
    return {
        "iterations": 0, "llm_calls": 0, "tool_calls": 0,
        "prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0,
        "usage_seen": False,
    }

def _emit_metrics(agg, session_id, device_id, outcome):
    logger.info("agent_turn_metrics", session_id=session_id, device_id=device_id,
                outcome=outcome, iterations=agg["iterations"], llm_calls=agg["llm_calls"],
                tool_calls=agg["tool_calls"],
                prompt_tokens=..., completion_tokens=..., total_tokens=...)
```

**优点**：

- ✓ 每个 turn 输出结构化指标
- ✓ outcome 区分（turn_complete / human_confirmation / max_iterations_reached）
- ✓ token 计量

**局限**：

- ✗ 是埋点，不是评测（埋点是数据采集，评测是质量判断）
- ✗ outcome 字段只反映"流程结束原因"，不反映"输出质量"
- ✗ 没有基于 outcome 的失败分类（仅记录）

### 3.4 test_react_loop_metrics.py（验证埋点而非评测）

来源：[`test_react_loop_metrics.py`](./../backend/tests/test_react_loop_metrics.py)

这是测试**指标埋点的正确性**，不是测试**Agent 输出质量**。

```python
def test_metrics_logged_on_turn_complete(db_session):
    ...
    MockLLM.return_value.chat_with_tools = AsyncMock(return_value=_resp("好的", None, ...))
    events = [e async for e in rl.run_agent_turn(session.id, "hi")]
    assert events[-1]["event"] == "turn_complete"
    calls = _metrics_calls(mock_log)
    assert len(calls) == 1
    kw = calls[0].kwargs
    assert kw["outcome"] == "turn_complete"
```

**评价**：mock LLM 返回固定响应，断言 metrics 被记录。这是**单元测试**，不是评测。

### 3.5 缺失项对照学习总结 §7

| 学习路线 §7 要求 | GEO2 现状 |
| --- | --- |
| 正常问题 15 条 | ✗ 无 |
| 边界问题 8 条 | ✗ 无 |
| 数据缺失 8 条 | ✗ 无 |
| 诱导错误 8 条 | ✗ 无 |
| 拒答 5 条 | ✗ 无 |
| 评测维度（准确性/完整性/相关性/可执行性/幻觉率） | ✗ 无 |
| 失败原因分类 | ✗ 仅 outcome 字段 |
| 可回归（CI 集成） | ✗ 无 |

## 4. 评分与理由

**评分：1 / 5（雏形）**

| 维度 | 现状 | 评分贡献 |
| --- | --- | --- |
| 单元测试覆盖 | 中等（覆盖关键模块） | +0.5 |
| 指标埋点 | ✓ Phase 1 已实现 | +0.5 |
| 评测集（30-50 条） | ✗ 无 | - |
| 5 类场景覆盖 | ✗ 无 | - |
| 失败原因分类 | ✗ 无 | - |
| 可回归 / CI 集成 | ✗ 无 | - |
| 人评结合 | ✗ 无 | - |

**关键证据**：

- 唯一证据：指标埋点（agent_turn_metrics）和单元测试
- 缺失：完整的评测体系（evals/、golden dataset、LLM-as-judge）

**与行业标准差距**：

- 学习路线 §7 是最低要求，30-50 条评测集
- GEO2 完全缺失，这是**面试最薄弱的一环**

## 5. 面试讲点

### 30 秒版本

> Phase 1 已实现指标埋点（prompt_tokens / iterations / outcome），单元测试覆盖关键模块；但**评测体系尚未建立** —— 没有 evals/、golden dataset、LLM-as-judge。

### 2 分钟版本

1. **已实现**：
   - Phase 1 指标埋点（每个 turn 输出 metrics）
   - 单元测试覆盖（test_*，关键模块覆盖）
2. **未实现**：
   - 评测集（无 evals/ 目录）
   - Golden dataset / ground truth
   - LLM-as-judge 评测
   - 失败原因分类（仅 outcome 字段）
   - CI 集成回归
3. **影响**：
   - 改 prompt / 模型时无法量化效果
   - 改工具描述时无法验证对 LLM 选择的影响
   - 面试时无法展示"质量如何被验证"

### 追问预判

| 追问 | 回答要点 |
| --- | --- |
| 为什么没建评测集？ | 项目阶段聚焦功能迭代，评测尚未排期（**改进候选 P0**） |
| 怎么判断一次改动变好还是变差？ | 只能看 metrics（tokens / iterations），不能看输出质量 |
| 评测集如何补齐？ | 先 30 条（5 类场景各几条），用 LLM-as-judge + 人工抽样验证 |
| 单元测试够用吗？ | 单元测试验证代码逻辑，不验证输出质量（本质不同） |

## 6. 改进建议

| 优先级 | 改进项 | 关联 |
| --- | --- | --- |
| **P0** | 建立 `evals/` 目录，先 30 条覆盖 5 类场景 | 见 `99-improvement-plan.md` |
| **P0** | LLM-as-judge 评测脚本（用 GPT-4o 评 MiniMax 输出） | 见 `99-improvement-plan.md` |
| **P0** | 失败原因分类（outcome + error type + retryable） | 见 `99-improvement-plan.md` |
| P1 | 评测集与 CI 集成（每次 commit 自动跑 evals） | 见 `99-improvement-plan.md` |
| P1 | 人评结合（每月抽 5% 评测集人评校准） | 见 `99-improvement-plan.md` |
| P2 | 评测可视化（baseline vs 当前版本的 pass rate） | 见 `99-improvement-plan.md` |

> **核心提示**：本维度是 GEO2 在面试场景下最薄弱的一环（评分 1/5）。如果只选一个改进项，**先建评测集**。

## 7. 面试风险提示

如果面试官问"你这个项目怎么验证质量的？"，按当前状态回答：

- ❌ "我们写了单元测试"（不够）
- ❌ "我们监控 token 使用"（不是评测）
- ✅ "目前主要是单元测试 + 指标埋点；评测集（evals/）正在建设"（诚实承认 + 改进意向）

**强烈建议**：在产出 `06-evaluation.md` 的同时，先建一个最小评测集（哪怕 10 条）作为"开始"的证据，可在面试中展示。