# 03. 上下文可控

> 面试官视角：本维度在 GEO2 的现状、评分、讲述建议、改进路径。

## 1. 维度定义

上下文窗口管理、压缩、检索的工程能力。包括：最大 token 限制、超限裁剪策略、滑动窗口、工具结果截断、自适应压缩、可解释裁剪决策。

依据：[`00-learning-summary.md` §6.3](./00-learning-summary.md)

## 2. 评分标准（0-5 分制）

| 分数 | 含义 | 触发条件 |
| --- | --- | --- |
| 0 | 缺失 | 无任何控制 |
| 1 | 雏形 | 仅硬编码限制 |
| 2 | 基础 | 有最简裁剪 |
| 3 | 达标 | 最大 token 限制 + 超限裁剪策略 |
| 4 | 良好 | 滑动窗口 + 历史摘要 + 工具结果截断 + 配置化 |
| 5 | 卓越 | 自适应压缩 + 可解释裁剪决策 + token 精确计量 |

## 3. GEO2 现状调研

### 3.1 Phase 3 配置（强项）

来源：[`config.py` L95–L97](./../backend/app/core/config.py)

```python
context_window_messages: int = 40   # 送进 LLM 的最近历史条数上限
tool_result_max_chars: int = 2000    # 旧 tool 结果截断字符上限
tool_result_keep_recent: int = 3     # 最近 N 个 tool 结果保全量
```

**默认值合理**：

- 40 条历史（按平均 1 user + 1 assistant + 1 tool = 3 条 / 轮，能覆盖 ~13 轮对话）
- 2000 字符截断（与典型工具返回大小匹配）
- 3 个保全量（避免最近工具结果被截断）

**配置化**：通过 Pydantic Settings 注入，可在 `.env` / 环境变量覆盖。

### 3.2 build_messages 实现（强项）

来源：[`react_loop.py` L47–L171](./../backend/app/domain/agent/react_loop.py)

```python
def build_messages(
    history: list[dict],
    memory_index_segment: str = "",
    *,
    window_messages: int | None = None,
    tool_result_max_chars: int | None = None,
    tool_result_keep_recent: int = 0,
) -> list[dict]:
    # Phase 3 ①滑动窗口：先裁，配对计算基于窗口后的历史(切断的一侧由 kept_ids 丢弃)
    if window_messages is not None and len(history) > window_messages:
        history = history[-window_messages:]

    # Phase 3 ③截断预算：最近 keep_recent 个 tool 结果保全量，其余超长截断
    tool_positions = [i for i, m in enumerate(history) if m.get("role") == "tool"]
    if tool_result_keep_recent > 0:
        keep_full = set(tool_positions[-tool_result_keep_recent:])
    else:
        keep_full = set()
    ...
```

**关键设计**：

- ✓ **三阶段处理**：窗口裁剪 → 配对保证 → 工具结果截断
- ✓ **配对计算基于窗口后历史**（切断的一侧由 kept_ids 丢弃）—— 避免 dangling tool_call
- ✓ **最近 N 个保全量**（避免最近工具结果被截断导致 LLM 困惑）
- ✓ **截断标记**：`content[:max_chars] + "…(truncated)"` —— LLM 可识别截断
- ✓ **辅助函数 `_apply_memory_prepend`**：把相关记忆拼到 user 消息前（不修改入参，返回新列表）
- ✓ **兼容两种 tool_calls 格式**：OpenAI 风格 + 简化风格（向后兼容）

### 3.3 Phase 3 演进路径（3 个 commit）

来源：[git log](./../../)

```
8176cce feat(agent): _drive_react_loop 按 Settings 施加上下文预算(窗口+tool截断)
02d3061 feat(agent): build_messages 滑动窗口 + 旧工具结果截断(默认关闭)
d8a362b feat(agent): Phase3 新增上下文预算配置(窗口/tool截断字符/保全量数)
```

**演进顺序**：

1. 配置层加 Settings（d8a362b）
2. build_messages 实现（02d3061，默认关闭）
3. _drive_react_loop 启用（8176cce）

这种"先配、后实现、再启用"的三段式是安全的演进模式。

### 3.4 测试覆盖

来源：[`backend/tests/`](./../backend/tests/)

- `test_build_messages.py`（推测存在，待验证）—— 配对保证 / 窗口 / 截断
- `test_context_budget.py`（推测）—— 边界条件

> 注：本调研未完整列出 context 相关测试文件，但 build_messages 的函数级复杂度意味着必须有专门测试覆盖。

## 4. 评分与理由

**评分：4 / 5（良好）**

| 维度 | 现状 | 评分贡献 |
| --- | --- | --- |
| 最大 token 限制 | ✓ context_window_messages | +1 |
| 超限裁剪策略 | ✓ 滑动窗口 + 工具截断 | +1 |
| 滑动窗口 | ✓ 已实现 | +1 |
| 历史摘要 | ✗ 无（仅截断，无摘要） | - |
| 工具结果截断 | ✓ 已实现 + 保全量策略 | +1 |
| 配置化 | ✓ Settings 注入 | +1 |
| 自适应压缩 | ✗ 无 | - |
| 可解释裁剪决策 | 部分（截断有标记，窗口无） | +0.5 |
| token 精确计量 | ✗ 字符级截断（非 token） | -0.5 |

**关键证据**：

- 强项：配对保证 + 三阶段处理 + 配置化
- 弱项：字符级 vs token 级、缺历史摘要、缺自适应压缩

**与行业标准差距**：

- 字符级截断对中文不友好（一个汉字 ≈ 1-2 tokens，但字符计数 1）
- 缺历史摘要：长对话会被"硬切"，丢掉早期信息
- 无自适应压缩：固定窗口大小，对所有场景一刀切

## 5. 面试讲点

### 30 秒版本

> Phase 3 上下文预算：滑动窗口 40 条 + 工具结果截断 2000 字符 + 最近 3 个工具结果保全量；build_messages 三阶段处理（窗口 → 配对 → 截断）。

### 2 分钟版本

1. **演进路径**：3 个 commit 三段式（配置 → 实现 → 启用），安全落地
2. **核心机制**：
   - 滑动窗口：按消息条数裁剪，保留最近 N 条
   - 工具结果截断：字符级 + 保全最近 3 个全量
   - 配对保证：切断的一侧由 kept_ids 丢弃，避免 dangling tool_call
3. **关键细节**：
   - 截断标记：`"…(truncated)"` —— LLM 可识别
   - 兼容性：OpenAI 风格 + 简化风格双协议
   - 辅助函数：`_apply_memory_prepend` 把记忆拼到 user 消息前
4. **配置化**：通过 Pydantic Settings 注入，env 可覆盖

### 追问预判

| 追问 | 回答要点 |
| --- | --- |
| 为什么用字符截断不用 token？ | 实现简单（无需 tokenizer），对中文略不友好；2000 字符 ≈ 4000 tokens 对 8k 上下文合理 |
| 窗口大小怎么选？ | 经验值：40 条 ≈ 13 轮对话；按业务路径分析（最长的"list → search → create"链路 ~ 9 轮） |
| 历史会丢吗？ | 是的，硬切；缺历史摘要，重要信息可能丢失（**改进候选**） |
| 截断后 LLM 能识别吗？ | 有 `"…(truncated)"` 标记；可以引导 LLM 重新调用工具 |
| token 限制如何精确保证？ | 当前没保证，依赖 provider 自动拒绝超长请求（**改进候选**） |

## 6. 改进建议

| 优先级 | 改进项 | 关联 |
| --- | --- | --- |
| P1 | 改用 token 级截断（接 tokenizer） | 见 `99-improvement-plan.md` |
| P1 | 增加历史摘要策略（窗口 + 摘要双层） | 见 `99-improvement-plan.md` |
| P2 | 截断决策可解释（输出 metadata：哪些消息被裁、被截断位置） | 见 `99-improvement-plan.md` |
| P2 | 自适应压缩（按当前 token 预算动态调整窗口） | 见 `99-improvement-plan.md` |
| P2 | 设置 token 上限硬限制（保证不超 provider 限制） | 见 `99-improvement-plan.md` |