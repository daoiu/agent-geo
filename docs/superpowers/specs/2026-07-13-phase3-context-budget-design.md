# GEO Agent Phase 3 — 上下文预算 设计

| 字段 | 值 |
|---|---|
| 版本 | 优化路线图 Phase 3 |
| 日期 | 2026-07-13 |
| 状态 | 设计中，待批 |
| 前置 | Phase 1（循环收敛 + 埋点）、Phase 2（记忆层向量化）已上线 |
| 路线图 | `2026-07-13-memory-context-optimization-roadmap.md` |
| 收敛项 | #4 工具结果瘦身（截断）+ #5 L0 滑动窗口 |
| 行为等价 | **是（默认宽松）**：新增参数默认关闭/宽松，短会话逐字节不变；仅长会话/大工具结果被裁 |

---

## 1. 背景与目标

### 1.1 背景

`build_messages`（`react_loop.py`）每轮把**整个 session 历史**全量转成 LLM 消息：

- **#4** 工具结果全量回灌：`search_knowledge` / `diagnose_brand` 的完整 JSON 存进 tool 消息，之后每轮重放，多轮线性膨胀。
- **#5** L0 无窗口：`list_messages` 全量加载，长会话 token 线性增长，逼近 context 上限。

Phase 1 已把两个入口收敛到单一 `build_messages`，本 Phase 只改这一处。

### 1.2 目标

1. **#5** `build_messages` 加**滑动窗口**：只发最近 N 条历史消息（+ system），旧的丢弃。
2. **#4** 旧**工具结果截断**：保留最近 M 个 tool 结果全量，更早的截断到 K 字符并标 `…(truncated)`。
3. 二者均**无 LLM**、纯省 token；**DB 永远存全量历史**，只裁"送进 LLM 的那份"，可逆。
4. **配置可调、默认宽松**：短会话/小结果逐字节不变，低风险；无真实基线时保守默认。

### 1.3 范围（In Scope）

| 模块 | 行为 |
|---|---|
| `build_messages` | 加 3 个可选参数：滑动窗口 + 旧 tool 结果截断；默认关闭则行为不变 |
| `_drive_react_loop` | 调 `build_messages` 时传入 Settings 派生的窗口/截断参数 |
| `Settings` | `context_window_messages` / `tool_result_max_chars` / `tool_result_keep_recent` |
| 测试 | 窗口裁剪 + tool 截断 + 配对不破 + 默认宽松不回归 |

### 1.4 范围外（Out of Scope）

| 项 | 原因 |
|---|---|
| 滚动摘要（LLM 蒸馏旧消息） | 用户拍板纯滑动窗口 |
| LLM 摘要旧工具结果 | 用户拍板截断 |
| tiktoken 精确 token 预算 | 用消息条数 + 字符数近似，YAGNI |
| 持久化裁剪后的历史 | DB 存全量，只裁发送副本 |
| 前端展示裁剪状态 | 无 |
| 基于 Phase 1 埋点自动调阈值 | 手动配置；用户未采集基线 |

## 2. 架构

### 2.1 唯一改动点：`build_messages`

```
history (全量, 来自 DB)
   │
   ├─ ① 滑动窗口:history = history[-window_messages:]  (window 生效时)
   │
   ├─ ② 配对计算 (现有 kept_ids 逻辑,在 windowed 上重算)
   │      窗口切断的 tool_call/结果 → 现有逻辑自动丢 dangling/orphan
   │
   └─ ③ 逐条 emit;tool 消息若非"最近 M 个"且超 K 字符 → 截断标记
```

> **关键**：窗口在配对计算**之前**应用。窗口可能切断某个 assistant 的 tool_call 与其
> tool 结果——现有 `kept_ids = resolved_ids & declared_ids`（`react_loop.py:69-83`）
> 天然把落单的一侧丢弃，不会产生 provider 400。故窗口与配对**自动兼容**，无需新逻辑。

### 2.2 默认宽松 = 低风险

| 参数 | 默认 | 效果 |
|---|---|---|
| `context_window_messages` | 40 | 历史 ≤ 40 条 → 不裁（多数 demo 会话） |
| `tool_result_max_chars` | 2000 | 单个 tool 结果 ≤ 2000 字符 → 不截 |
| `tool_result_keep_recent` | 3 | 最近 3 个 tool 结果永远全量 |

短会话 + 小结果 → 三者都不触发 → `build_messages` 输出逐字节等价于 Phase 2。

### 2.3 关键设计原则

| 原则 | 选择 | 理由 |
|---|---|---|
| 裁剪位置 | 仅 `build_messages`（发送副本） | DB 存全量，可逆；Phase 1 已收敛为一处 |
| tool 瘦身 | 截断（无 LLM） | 用户拍板；省 token 不加成本 |
| L0 控制 | 纯滑动窗口（无 LLM） | 用户拍板；最简 |
| 配对兼容 | 窗口先于配对计算 | 复用现有 dangling/orphan 丢弃逻辑 |
| 参数默认 | 宽松（40 / 2000 / 3） | 无基线时保守，短会话零影响 |
| 参数注入 | build_messages 可选参数，默认 None/0 | 现有 build_messages 测试不传 → 行为不变 |

## 3. 接口规范

### 3.1 `build_messages` 新签名

```python
def build_messages(
    history: list[dict],
    memory_index_segment: str = "",
    *,
    window_messages: int | None = None,      # None → 不裁
    tool_result_max_chars: int | None = None,  # None → 不截
    tool_result_keep_recent: int = 0,          # 最近 N 个 tool 结果保全量
) -> list[dict]: ...
```

- `window_messages=None`（默认）→ 不做窗口（现有测试全部走此路径，行为不变）
- `tool_result_max_chars=None`（默认）→ 不做截断
- 截断标记：内容 `[:max]` + `"…(truncated)"`

### 3.2 `_drive_react_loop` 传参

```python
settings = get_settings()
messages = build_messages(
    history,
    memory_index_segment=memory_index_segment,
    window_messages=settings.context_window_messages,
    tool_result_max_chars=settings.tool_result_max_chars,
    tool_result_keep_recent=settings.tool_result_keep_recent,
)
```

### 3.3 Settings

```python
context_window_messages: int = 40     # 送进 LLM 的最近历史条数上限
tool_result_max_chars: int = 2000      # 旧 tool 结果截断字符上限
tool_result_keep_recent: int = 3       # 最近 N 个 tool 结果保全量
```

## 4. 截断规则细节

在（可能已窗口化的）history 上：

1. 找出所有 `role == "tool"` 消息的位置 `tool_positions`
2. `keep_full = set(tool_positions[-tool_result_keep_recent:])`（`keep_recent=0` → 空集）
3. emit tool 消息时，若其位置 ∉ `keep_full` 且 `tool_result_max_chars` 非 None 且
   `len(content) > tool_result_max_chars` → `content = content[:max] + "…(truncated)"`

截断只改 tool 消息 **content**，不动结构 → 配对逻辑不受影响。

## 5. 数据流

- DB 落库、SSE 事件、工具执行、记忆注入**全部不变**
- 仅 `build_messages` 产出的 LLM 消息列表在长会话/大结果时变小
- 每轮 reload history 仍从 DB 取全量；裁剪只发生在 build 阶段

## 6. 错误处理 / 边界

| 场景 | 行为 |
|---|---|
| 历史 ≤ window | 不裁（`history[-40:]` 当 len<40 返回全部） |
| window 切断 tool_call/结果配对 | 现有 `kept_ids` 逻辑丢落单一侧，无 400 |
| 最新 user 消息 | 永在窗口内（末条），不会被裁 |
| 记忆 relevant 注入 | 作用于窗口内第一条 user 消息，不受影响 |
| tool 结果恰好 = max | 不截（严格 `>`） |
| 截断后 JSON 不合法 | 无妨——tool content 对 LLM 是文本上下文，非结构化解析 |

## 7. 文件地图

```
backend/app/
├── core/config.py                 # 改: +3 settings
├── domain/agent/react_loop.py     # 改: build_messages 加 3 参数 + 截断/窗口逻辑;
│                                   #     _drive_react_loop 传参
└── tests/
    ├── test_react_loop.py         # 改/加: 窗口 + 截断 + 配对不破 + 默认不变
    └── test_context_budget.py     # 新(可选): 专测窗口/截断纯函数行为
```

## 8. 测试

| 层 | 用例 |
|---|---|
| 窗口 | 历史 > N → 只留最近 N；≤ N → 全留；system 恒在首 |
| 窗口 × 配对 | 窗口切断 tool_call → dangling 被丢，无孤儿 tool；不抛 |
| 截断 | 旧 tool 结果超 K → 截断标记；最近 keep_recent 个全量；短结果不截 |
| 截断边界 | 恰好 = K 不截；keep_recent=0 全截；keep_recent≥数量 全留 |
| 默认不变 | 不传新参数（None/0）→ 输出与 Phase 2 逐条一致（现有 build_messages 测试即回归）|
| 集成 | `_drive_react_loop` 传 Settings 参数后 turn 正常，事件流不变 |

mock 策略：`build_messages` 是纯函数，直接构造 history 断言输出，无需 DB/LLM。

## 9. 决策日志

| 决策 | 选项 | 选择 | 理由 |
|---|---|---|---|
| 工具瘦身 | 截断 / LLM 摘要 | 截断 | 用户拍板；省 token 不加 LLM 成本 |
| L0 控制 | 滑动窗口 / 窗口+滚动摘要 | 纯滑动窗口 | 用户拍板；最简 |
| 裁剪位置 | DB / 发送副本 | 发送副本（build_messages） | 可逆；DB 存全量 |
| 参数默认 | 激进 / 宽松 | 宽松（40/2000/3） | 无基线时保守，短会话零影响 |
| 窗口 vs 配对顺序 | 配对先 / 窗口先 | 窗口先 | 复用现有 dangling 丢弃，无新逻辑 |
| token 度量 | tiktoken / 条数+字符 | 条数+字符近似 | YAGNI；无需精确 |

## 10. 观测（只记录）

- 无基线数据下，40 / 2000 / 3 是经验默认；采集 Phase 1 埋点后可据实调整（改 Settings 即可，无需改码）。
- 若未来要"按 token 预算"而非"按条数"裁，可在此扩展；当前 YAGNI。

## 11. 退出标准

- [ ] 历史 > `context_window_messages` 时只发最近 N 条 + system
- [ ] 旧 tool 结果超 `tool_result_max_chars` 被截断并标记；最近 `keep_recent` 个保全量
- [ ] 窗口切断的 tool_call/结果不产生 provider 400（配对逻辑兜住）
- [ ] 不传新参数时 `build_messages` 输出与 Phase 2 逐条一致（现有测试全绿）
- [ ] 后端全量单测通过
- [ ] DB 落库 / SSE / 记忆注入行为不变
