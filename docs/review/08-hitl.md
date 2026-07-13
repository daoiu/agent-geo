# 08. HITL（Human-in-the-loop）

> 面试官视角：本维度在 GEO2 的现状、评分、讲述建议、改进路径。

## 1. 维度定义

Human-in-the-loop 关键节点的确认流。包括：高风险操作确认、可中断可继续、可配置策略、用户反馈回路、超时处理。

依据：[`00-learning-summary.md` §6.8](./00-learning-summary.md)

> 本维度与 04-permission 有重叠（04 关注权限分级与确认机制；08 关注完整 HITL 流程与反馈回路）。

## 2. 评分标准（0-5 分制）

| 分数 | 含义 | 触发条件 |
| --- | --- | --- |
| 0 | 缺失 | 无 HITL |
| 1 | 雏形 | 仅有注释/意向 |
| 2 | 基础 | 有确认流但不完整 |
| 3 | 达标 | 高风险操作有确认 |
| 4 | 良好 | 确认流可中断可继续 |
| 5 | 卓越 | 可配置策略 + 用户反馈回路 |

## 3. GEO2 现状调研

### 3.1 HITL 事件清单（覆盖度有限）

来源：grep `human.?confirmation|HITL|user.?approval` 在 `backend/app`

| 事件 | 来源 | 用途 |
| --- | --- | --- |
| `human_confirmation_required` | react_loop | 写类工具需确认 |
| 端点 `/sessions/.../messages/.../confirm` | agent_chat API | 用户 approve/reject |
| `run_agent_turn_from_checkpoint` | react_loop | 断点续跑 |

**仅 1 类 HITL 事件**：写类工具的二次确认。

**缺失的 HITL 场景**：

- ✗ 用户决策类（"选 A 还是 B"）
- ✗ 用户输入补充（"再给我一个指标"）
- ✗ 敏感操作的多步审批（v0.4 设计有此意图但未实施）
- ✗ 长任务的进度确认（"已生成 3/10 是否继续"）

### 3.2 确认流的可中断可继续（强项）

来源：[`agent_chat.py` L74–L127](./../backend/app/api/agent_chat.py) + [`react_loop.py` L447–L577`](./../backend/app/domain/agent/react_loop.py)

**approve 流程**：

1. 前端弹窗 → POST `/sessions/{sid}/messages/{mid}/confirm {approved: true}`
2. API 层：`confirm_message(message_id, approved=True)` 标记 resolved
3. API 层：`run_agent_turn_from_checkpoint(session_id, message_id, ...)` 启动断点续跑
4. 流式 SSE 返回续跑结果

**reject 流程**：

1. 前端弹窗 → POST `{approved: false}`
2. API 层：`confirm_message(message_id, approved=False)`
3. 追加 "取消" 用户消息 + "好的，已取消。" 助手消息
4. 返回 JSON `{status: 'cancelled'}`

**优点**：

- ✓ approve / reject 都明确处理
- ✓ reject 追加消息（用户决策可追溯）
- ✓ approve 走断点续跑（保持 Agent Loop 上下文）

### 3.3 断点续跑机制（强项）

来源：[`react_loop.py` L447–L577](./../backend/app/domain/agent/react_loop.py)

```python
async def run_agent_turn_from_checkpoint(
    session_id: str,
    checkpoint_message_id: str,
    device_id: str | None = None,
) -> AsyncIterator[dict]:
    """从 pending_confirmation 消息处继续执行。
    ...
    6. 继续 ReAct 循环（委托共享驱动，基于新 tool 结果继续决策）
    """
```

**优点**：

- ✓ 完整断点恢复逻辑（从 checkpoint_message_id 找到原 tool_call）
- ✓ 解析两种格式（OpenAI 风格 + 简化风格）
- ✓ 委托到 `_drive_react_loop` 共享循环体（保持一致性）
- ✓ 异常处理（NotImplementedError / 其他异常都 yield error）

### 3.4 ⚠️ 缺失：HITL 策略配置化

当前设计：

```python
# tool_executor.py L58-L61
if tool_name == "generate_article":
    return await self._execute_generate_article(validated)
```

**问题**：

- ✗ HITL 策略 hard-coded 在 `tool_executor.py` 的 `if/elif` 链
- ✗ 添加工具时需修改两处（tool 定义 + executor 分支）
- ✗ 无 per-tool `requires_confirmation: bool` 声明
- ✗ 无 per-user 策略（不同用户不同确认策略）

### 3.5 ⚠️ 缺失：用户反馈回路

**当前设计**：HITL 仅用于"approve/reject 一次性操作"，不进入模型决策。

**理想设计**：

- 用户拒绝某工具调用 → 该拒绝理由进入 LLM 上下文，影响后续决策
- 用户确认某操作 → 标记该操作为"用户偏好"，未来类似操作不再询问

GEO2 **没有**实现这种反馈回路。

### 3.6 ⚠️ 缺失：HITL 超时处理

**当前设计**：

- DB 保留 `pending_confirmation=1`
- 用户不操作 → 永久 pending
- 后端无超时自动取消

**理想设计**：

- pending > N 分钟 → 自动取消 + 追加"超时取消"消息
- 防止 pending 状态堆积

### 3.7 测试覆盖

来源：[`backend/tests/`](./../backend/tests/) —— 没有专门的 `test_hitl.py` 或 `test_confirmation_flow.py`。

确认机制覆盖在：

- `test_api_agent_chat.py`（API 集成测试）
- `test_react_loop_metrics.py`（埋点测试，验证 outcome=human_confirmation）

**缺口**：缺少端到端的 HITL 流程测试（approve → 续跑 → 完成 / reject → 取消 → 消息）。

## 4. 评分与理由

**评分：3 / 5（达标，但深度不足）**

| 维度 | 现状 | 评分贡献 |
| --- | --- | --- |
| 高风险操作确认 | ✓ generate_article 抛 HumanConfirmationRequired | +1 |
| 确认流可中断可继续 | ✓ approve 走断点续跑、reject 追加消息 | +1 |
| 多种 HITL 场景 | ✗ 仅 1 类（写类工具二次确认） | - |
| 策略配置化 | ✗ hard-coded | - |
| 用户反馈回路 | ✗ 无 | - |
| 超时处理 | ✗ 无 | - |
| HITL 测试 | 部分（API 集成） | +0.5 |

**关键证据**：

- 强项：approve/reject 流程完整 + 断点续跑
- 弱项：HITL 覆盖度窄（仅 1 类事件）+ 无配置化 + 无反馈回路

**与行业标准差距**：

- 学习路线 §6.8 卓越标准：可配置策略 + 用户反馈回路
- GEO2 仅达到"高风险操作有确认" + "可中断可继续"

## 5. 面试讲点

### 30 秒版本

> generate_article 抛 HumanConfirmationRequired 暂停 ReAct 循环；approve 走断点续跑、reject 追加取消消息；DB 持久化 pending_confirmation。覆盖度窄（仅 1 类事件），无配置化和反馈回路。

### 2 分钟版本

1. **核心机制**：
   - HumanConfirmationRequired 异常驱动暂停
   - approve 走断点续跑（保持 Loop 上下文）
   - reject 追加"取消"消息（用户决策可追溯）
2. **断点续跑**：run_agent_turn_from_checkpoint 解析 checkpoint_message_id，调 _execute_generate_article_confirmed，再委托 _drive_react_loop
3. **覆盖度**：
   - ✓ 写类工具二次确认
   - ✗ 用户决策类（选 A/B）
   - ✗ 用户输入补充
   - ✗ 多步审批
   - ✗ 长任务进度确认
4. **改进方向**：策略配置化、用户反馈回路、超时处理

### 追问预判

| 追问 | 回答要点 |
| --- | --- |
| HITL 覆盖哪些场景？ | 当前仅"写类工具二次确认"；未来要扩展到用户决策、补充输入 |
| 用户拒绝后 LLM 知道吗？ | 当前不知道（reject 仅追加消息，不进入 LLM 上下文） |
| pending 状态能超时吗？ | 当前不能（**改进候选 P1**） |
| 多个 HITL 操作能并行吗？ | 不能（每个 turn 只有一个 pending_confirmation） |
| 怎么让策略可配置？ | 每个工具声明 requires_confirmation: bool；或在 Settings 中配置 |

## 6. 改进建议

| 优先级 | 改进项 | 关联 |
| --- | --- | --- |
| P1 | 声明式 HITL 策略（per-tool `requires_confirmation`） | 见 `99-improvement-plan.md` |
| P1 | pending 超时自动取消（默认 5 分钟） | 见 `99-improvement-plan.md` |
| P1 | reject 理由进入 LLM 上下文（影响后续决策） | 见 `99-improvement-plan.md` |
| P2 | 用户偏好学习（"用户偏好类 A 文章风格"） | 见 `99-improvement-plan.md` |
| P2 | 多类 HITL 事件（决策、补充输入、进度确认） | 见 `99-improvement-plan.md` |
| P2 | HITL 端到端测试套件 | 见 `99-improvement-plan.md` |