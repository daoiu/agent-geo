# Phase 3 上下文预算 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 给 `build_messages` 加滑动窗口 + 旧工具结果截断，只裁"送进 LLM 的那份"消息，长会话/大结果省 token，短会话逐字节不变。

**Architecture:** 唯一改动点是 Phase 1 收敛出的 `build_messages`（纯函数）。新增 3 个可选参数（默认关闭）：滑动窗口先于配对计算（复用现有 dangling/orphan 丢弃逻辑），旧 tool 结果按位置截断。`_drive_react_loop` 从 Settings 读参数传入。DB 永远存全量历史。

**Tech Stack:** Python 3.11 / pytest（纯函数测试，无 DB/LLM）

## Global Constraints

- **只改 `build_messages`（发送副本）**，不动 DB 落库 / SSE / 工具执行 / 记忆注入。DB 永远存全量历史。
- **新参数默认关闭/宽松**：`window_messages=None` / `tool_result_max_chars=None` / `tool_result_keep_recent=0` → 现有 build_messages 测试不传即行为逐字节不变。
- **窗口先于配对计算**：窗口切断的 tool_call/结果由现有 `kept_ids = resolved_ids & declared_ids`（`react_loop.py`）丢弃落单一侧，不产生 provider 400。
- **截断只改 tool 消息 content**（`content[:max] + "…(truncated)"`），不动结构，配对不受影响。严格 `>` 判定（恰好 = max 不截）。
- **Settings 默认**：`context_window_messages: int = 40` / `tool_result_max_chars: int = 2000` / `tool_result_keep_recent: int = 3`。
- **均无 LLM**。

---

### Task 1: Settings 三个上下文预算配置项

**Files:**
- Modify: `backend/app/core/config.py`（`memory_extract_min_chars` 附近）
- Test: `backend/tests/test_react_loop.py`（加 Settings 断言）

**Interfaces:**
- Produces: `Settings.context_window_messages: int = 40`、`Settings.tool_result_max_chars: int = 2000`、`Settings.tool_result_keep_recent: int = 3`

- [ ] **Step 1: 写失败测试**

在 `backend/tests/test_react_loop.py` 末尾追加：

```python
def test_phase3_settings_defaults():
    from app.core.config import Settings
    s = Settings(deepseek_api_key="x")
    assert s.context_window_messages == 40
    assert s.tool_result_max_chars == 2000
    assert s.tool_result_keep_recent == 3
```

- [ ] **Step 2: 运行确认失败**

Run: `cd /d/GEO2/backend && python -m pytest tests/test_react_loop.py::test_phase3_settings_defaults -q`
Expected: FAIL —— `AttributeError: 'Settings' object has no attribute 'context_window_messages'`

- [ ] **Step 3: 加配置项**

在 `backend/app/core/config.py` 的 `memory_extract_min_chars: int = 8` 行下方加：

```python
    # Phase 3 — 上下文预算
    context_window_messages: int = 40   # 送进 LLM 的最近历史条数上限
    tool_result_max_chars: int = 2000    # 旧 tool 结果截断字符上限
    tool_result_keep_recent: int = 3     # 最近 N 个 tool 结果保全量
```

- [ ] **Step 4: 运行确认通过**

Run: `cd /d/GEO2/backend && python -m pytest tests/test_react_loop.py::test_phase3_settings_defaults -q`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
cd /d/GEO2 && git add backend/app/core/config.py backend/tests/test_react_loop.py
git commit -m "feat(agent): Phase3 新增上下文预算配置(窗口/tool截断字符/保全量数)"
```

---

### Task 2: build_messages 滑动窗口 + 旧 tool 结果截断

**Files:**
- Modify: `backend/app/domain/agent/react_loop.py`（`build_messages` 加 3 参数 + 窗口/截断逻辑）
- Test: `backend/tests/test_react_loop.py`（加窗口/截断/配对/默认不变用例）

**Interfaces:**
- Produces: `build_messages(history, memory_index_segment="", *, window_messages=None, tool_result_max_chars=None, tool_result_keep_recent=0) -> list[dict]`

- [ ] **Step 1: 写失败测试**

在 `backend/tests/test_react_loop.py` 加（文件已 `import json` / `from app.domain.agent.react_loop import build_messages`）：

```python
def test_build_messages_window_keeps_last_n():
    history = [{"role": "user", "content": f"m{i}"} for i in range(10)]
    messages = build_messages(history, window_messages=3)
    # system + 最近 3 条
    assert messages[0]["role"] == "system"
    assert [m["content"] for m in messages[1:]] == ["m7", "m8", "m9"]


def test_build_messages_window_none_keeps_all():
    history = [{"role": "user", "content": f"m{i}"} for i in range(10)]
    messages = build_messages(history)  # 默认不裁
    assert len([m for m in messages if m["role"] == "user"]) == 10


def test_build_messages_window_drops_dangling_pair():
    # 窗口切断:assistant tool_call 落在窗外,只留 tool 结果 → 孤儿被丢
    history = [
        {"role": "user", "content": "老消息填充1"},
        {"role": "assistant", "content": None,
         "tool_calls": [{"id": "tc1", "function": {"name": "x", "arguments": "{}"}}]},
        {"role": "tool", "tool_call_id": "tc1", "content": "result"},
        {"role": "user", "content": "新消息"},
    ]
    # 窗口=2 → 只留最后 2 条(tool 结果 + user);tc1 的 assistant 声明被切掉
    messages = build_messages(history, window_messages=2)
    assert all(m.get("role") != "tool" for m in messages)  # 孤儿 tool 被丢


def test_build_messages_truncates_old_tool_result():
    big = "x" * 5000
    history = [
        {"role": "assistant", "content": None,
         "tool_calls": [{"id": "a", "function": {"name": "t", "arguments": "{}"}}]},
        {"role": "tool", "tool_call_id": "a", "content": big},
        {"role": "assistant", "content": None,
         "tool_calls": [{"id": "b", "function": {"name": "t", "arguments": "{}"}}]},
        {"role": "tool", "tool_call_id": "b", "content": "recent"},
    ]
    # keep_recent=1 → 最近 1 个 tool(b) 全量;a 被截
    messages = build_messages(history, tool_result_max_chars=100,
                              tool_result_keep_recent=1)
    tool_msgs = [m for m in messages if m.get("role") == "tool"]
    a_msg = next(m for m in tool_msgs if m["tool_call_id"] == "a")
    b_msg = next(m for m in tool_msgs if m["tool_call_id"] == "b")
    assert a_msg["content"].endswith("…(truncated)")
    assert len(a_msg["content"]) <= 100 + len("…(truncated)")
    assert b_msg["content"] == "recent"  # 最近的全量


def test_build_messages_truncate_boundary_not_cut():
    exact = "y" * 100
    history = [
        {"role": "assistant", "content": None,
         "tool_calls": [{"id": "a", "function": {"name": "t", "arguments": "{}"}}]},
        {"role": "tool", "tool_call_id": "a", "content": exact},
    ]
    # 恰好 = max 且 keep_recent=0 → 不截(严格 >)
    messages = build_messages(history, tool_result_max_chars=100,
                              tool_result_keep_recent=0)
    tool_msg = next(m for m in messages if m.get("role") == "tool")
    assert tool_msg["content"] == exact
```

- [ ] **Step 2: 运行确认失败**

Run: `cd /d/GEO2/backend && python -m pytest tests/test_react_loop.py -k "window or truncate" -q`
Expected: FAIL —— `build_messages() got an unexpected keyword argument 'window_messages'`

- [ ] **Step 3: 实现窗口 + 截断**

改 `backend/app/domain/agent/react_loop.py` 的 `build_messages`。当前签名：

```python
def build_messages(
    history: list[dict],
    memory_index_segment: str = "",
) -> list[dict]:
```

替换为（新签名 + 开头加窗口，配对计算前）：

```python
def build_messages(
    history: list[dict],
    memory_index_segment: str = "",
    *,
    window_messages: int | None = None,
    tool_result_max_chars: int | None = None,
    tool_result_keep_recent: int = 0,
) -> list[dict]:
    # Phase 3 ①滑动窗口:先裁,配对计算基于窗口后的历史(切断的一侧由 kept_ids 丢弃)
    if window_messages is not None and len(history) > window_messages:
        history = history[-window_messages:]

    # Phase 3 ③截断:预算最近 keep_recent 个 tool 结果保全量,其余超长截断
    tool_positions = [i for i, m in enumerate(history) if m.get("role") == "tool"]
    if tool_result_keep_recent > 0:
        keep_full = set(tool_positions[-tool_result_keep_recent:])
    else:
        keep_full = set()
```

然后原有的 `resolved_ids` / `declared_ids` / `kept_ids` 计算与 `out` 构建**保持不变**（它们现在基于窗口后的 history）。只需在 emit `tool` 消息处加截断。找到：

```python
        elif role == "tool":
            # 只发能对上 assistant tool_call 的结果；孤儿 tool 跳过
            if msg.get("tool_call_id") in kept_ids:
                out.append({
                    "role": "tool",
                    "tool_call_id": msg["tool_call_id"],
                    "content": msg["content"],
                })
```

替换为（用 `enumerate` 拿到位置以判断是否 keep_full）：

```python
        elif role == "tool":
            # 只发能对上 assistant tool_call 的结果；孤儿 tool 跳过
            if msg.get("tool_call_id") in kept_ids:
                content = msg["content"]
                if (tool_result_max_chars is not None
                        and idx not in keep_full
                        and isinstance(content, str)
                        and len(content) > tool_result_max_chars):
                    content = content[:tool_result_max_chars] + "…(truncated)"
                out.append({
                    "role": "tool",
                    "tool_call_id": msg["tool_call_id"],
                    "content": content,
                })
```

这要求外层遍历带位置索引。找到 `for msg in history:` 改为 `for idx, msg in enumerate(history):`。

- [ ] **Step 4: 运行确认通过**

Run: `cd /d/GEO2/backend && python -m pytest tests/test_react_loop.py -q`
Expected: PASS（新窗口/截断用例 + 现有 build_messages 用例全绿——现有用例不传新参数，行为不变）

- [ ] **Step 5: 提交**

```bash
cd /d/GEO2 && git add backend/app/domain/agent/react_loop.py backend/tests/test_react_loop.py
git commit -m "feat(agent): build_messages 滑动窗口 + 旧工具结果截断(默认关闭)"
```

---

### Task 3: _drive_react_loop 传入 Settings 预算参数 + 全量回归

**Files:**
- Modify: `backend/app/domain/agent/react_loop.py`（`_drive_react_loop` 调 build_messages 传参）
- Test: 全量

**Interfaces:**
- Consumes: `build_messages` 新参数（Task 2）；`Settings` 三个字段（Task 1）

- [ ] **Step 1: 找到 _drive_react_loop 里的 build_messages 调用**

Run: `cd /d/GEO2/backend && grep -n "build_messages(history" app/domain/agent/react_loop.py`
Expected: 一处（`_drive_react_loop` 内），形如 `messages = build_messages(history, memory_index_segment=memory_index_segment)`

- [ ] **Step 2: 改为传 Settings 参数**

`_drive_react_loop` 内已有 `settings = get_settings()`（Phase 1 收敛后创建 llm 用）。若无则在函数顶部加 `settings = get_settings()`。把该 build_messages 调用替换为：

```python
        messages = build_messages(
            history,
            memory_index_segment=memory_index_segment,
            window_messages=settings.context_window_messages,
            tool_result_max_chars=settings.tool_result_max_chars,
            tool_result_keep_recent=settings.tool_result_keep_recent,
        )
```

> 确认 `_drive_react_loop` 顶部有 `settings = get_settings()`（Phase 1 里 `llm = LLMClient(settings)` 之前那行）。若因重构已改名/删除，则补 `settings = get_settings()`。

- [ ] **Step 3: 跑 react_loop 相关（单文件隔离）**

Run: `cd /d/GEO2/backend && python -m pytest tests/test_react_loop.py -q`
Expected: PASS（默认 40 条窗口 > 测试里的短历史，不裁 → 行为不变）

- [ ] **Step 4: 全量回归**

Run: `cd /d/GEO2/backend && python -m pytest -q`
Expected: PASS（全部通过；预计 ~10-12 分钟。默认宽松，短会话测试不受窗口/截断影响）

- [ ] **Step 5: 提交**

```bash
cd /d/GEO2 && git add backend/app/domain/agent/react_loop.py
git commit -m "feat(agent): _drive_react_loop 按 Settings 施加上下文预算 + 全量回归"
```

---

## 自查（Self-Review）

**Spec 覆盖：**
- spec §1.2 #5 滑动窗口 → Task 2（window_messages）✓
- spec §1.2 #4 tool 截断 → Task 2（tool_result_max_chars/keep_recent）✓
- spec §2.1 窗口先于配对 → Task 2 Step 3（窗口在 kept_ids 计算前）✓
- spec §3.1 build_messages 新签名 → Task 2 ✓
- spec §3.2 _drive_react_loop 传参 → Task 3 ✓
- spec §3.3 Settings → Task 1 ✓
- spec §4 截断规则（tool_positions / keep_full / 严格 >）→ Task 2 Step 3 + 测试 ✓
- spec §6 边界（≤window 不裁 / 切断配对 / 恰好=max / 最新 user 在窗内）→ Task 2 测试 ✓
- spec §8 测试矩阵 → Task 2 + Task 3 ✓
- spec §11 退出标准 → 各 Task ✓

**类型一致性：** `build_messages(..., window_messages, tool_result_max_chars, tool_result_keep_recent)` 命名在 Task 1（Settings 字段）/ Task 2（参数）/ Task 3（传参）三处一致；截断标记 `"…(truncated)"` 统一 ✓

**占位扫描：** 无 TBD/TODO；每个 code step 附完整代码。Task 3 Step 2 "确认 settings 存在"是操作核对指引，非占位 ✓
