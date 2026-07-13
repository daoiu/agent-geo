# GEO Agent L2 记忆层 — v0.6 P1.6 设计

| 字段 | 值 |
|---|---|
| 版本 | v0.6（Agent L2 跨会话偏好） |
| 日期 | 2026-07-13 |
| 状态 | 设计已批，待实施 |
| 前置 | v0.6 P1.5（ContentWriterAgent + 文章下载）已上线 |
| 后端变更 | 增 deps 依赖 / MemoryRepository / MemoryService / AgentMemoryORM / react_loop 3 处微调 / agent_chat 2 处接 deps / Settings +1 |
| 前端变更 | 增 deviceId util / client.ts 3 处加 `X-Device-Id` header |

参考 `D:\Agent\learn-claude-code\s09_memory`（s09 Memory）与 `D:\Agent\ai-agent-interview-guide\docs\01-面试八股文\05-记忆系统.md`（分层框架）。

---

## 1. 背景与目标

### 1.1 背景

GEO2 Agent 当前的"记忆"只有一层:**L0 情景记忆** = `AgentMessageORM`,同一 session 内 ReAct loop 全量塞历史。对应 s09/Claude Code 的"L0 conversation buffer"。

L0 缺三件事:
- **跨 session 偏好** — 用户说"记住北北云吞是潮汕口味",下次开新 session 还能复用到
- **对话摘要蒸馏** — L0 越长越贵,需要从 L0 提炼稳定事实/偏好存为小而准的池子
- **品牌/项目上下文** — 反复出现的项目背景应当常驻 system

### 1.2 目标

1. 在 GEO2 中补全 **L2 偏好/事实层** — 跨 session 自动蒸馏稳定事实与偏好
2. 引入 **device_id 身份管道** — 前端生成 + 请求头传递,后端用作 L2 的 scope key
3. 不破坏 L0（消息持久化）、L1（KB）任意一层
4. 不引入 embedding/向量库/MemGPT 分页/记忆图谱/反思模块

### 1.3 范围（In Scope）

| 模块 | 行为 |
|---|---|
| 前端 device_id | `localStorage` 持久化,`crypto.randomUUID()` 生成,`X-Device-Id` header 注入所有 fetch |
| 后端 device_id 依赖 | FastAPI `Header()` 依赖,UUID 校验,非法/缺失静默 None |
| `AgentMemoryORM` | 跨 session 偏好存储（1 张表） |
| `MemoryRepository` | CRUD + scope 查询 + 整理用 replace_all_bulk |
| `MemoryService` | 7 个函数（照搬 s09 命名）：write_memory / read_memory_index / select_relevant / load_relevant_memories / extract / consolidate / build_memory_segment |
| `Settings` | `memory_consolidate_threshold: int = 50` |
| `react_loop` 接入 | system prompt 拼索引段;每个 user turn 一次性注入相关记忆;turn_complete 后 fire-and-forget 触发 extract |
| `agent_chat` API | 读 `device_id_header` 依赖,传到 react_loop |
| 测试 | backend ~15 cases + frontend ~6 cases |

### 1.4 范围外（Out of Scope,本期不做）

| 项 | 原因 |
|---|---|
| L0 摘要压缩 | 当前 session 内全量塞历史够用 |
| L1 KB 替代 | KB 用户手动管理,本来正交 |
| agent memory tool 暴露（remember/recall/forget） | 本期仅被动提取 |
| 重要度评分字段 | 用户 7-13 拍板不做 |
| 三因子打分（相关性 + 近期性 + 重要性） | 用户 7-13 拍板不做 |
| 注入安全过滤（防 prompt injection） | 用户 7-13 拍板不做 |
| `embedding_model_version` 字段预留 | 用户 7-13 拍板不做 |
| Dream 多门控（时间/扫描/会话/锁） | 用户 7-13 拍板不做（只留"行数 ≥ 阈值"） |
| MemGPT 分页/外溢 | 过度工程 |
| 记忆图谱（实体关系） | 当前域不需要 |
| 反思模块 | 与 Dream 重复 |
| 时间衰减 `exp(-λt)` | Dream 自然淘汰过期即可 |
| 用户 user 体系 | 当前为匿名 demo，device_id 已能跨 session |
| 前端 UI（记忆列表/编辑/删除） | 无 |
| 记忆数据导出/迁移 | 无 |

## 2. 用户与场景

### 2.1 目标用户

GEO2 demo 阶段的本地工具使用者（单人本地浏览器），不是 SaaS 多租户。

### 2.2 核心场景

| # | 场景 | 期望 |
|---|---|---|
| 1 | 用户说"北北云吞是潮汕口味，以后都按这个调" | LLM 提取 → 写入 L2（type=project）→ 下次开新 agent session 能看到这条 |
| 2 | 跨多 session 反复要求"风格简洁、不要 emoji" | 摘要成 `feedback` 类单条,常驻 system 索引 |
| 3 | 用户上传 KB 后让 agent 引用 | KB 属于 L1，与 L2 正交，不改 |
| 4 | 用户清浏览器数据 | `localStorage` 清掉 → device_id 重生 → 旧记忆失效（scope 不再匹配） |
| 5 | 玩家关掉 Dark Reader / 开无痕模式 | device_id 重新生成，等同清浏览器数据 |
| 6 | LLM 调用失败 | extract 失败不阻塞 turn 响应,fire-and-forget 静默 |

### 2.3 成功标准

- 跨 session 复现偏好（场景 1-2）
- 已有功能（诊断 / KB / 文章 / 发布 / 监测）端到端不回归
- 后端 442+ 单测全部 pass（基线 v0.6 P1.5 后,本次新增 ~32）
- 前端 87+ 单测全部 pass（基线 v0.6 P1.5 后,本次新增 7）

## 3. 架构

### 3.1 在栈中的位置

```
┌─────────────── Frontend ────────────────┐
│  deviceId.ts (新) → X-Device-Id header  │
└────────────┬────────────────────────────┘
             │ /api/agent/...
             ▼
┌─────────────── Backend ────────────────┐
│  deps.py: device_id_header()           │
│  agent_chat.py: pass through           │
│  → react_loop.py (参数化 device_id)    │
│     ├─ build_messages 拼 memory 索引   │
│     ├─ load_relevant 注入 user turn    │
│     └─ turn_complete 后 fire-forget    │
│        extract_memories                │
└─────────────────────────────────────────┘
```

L2 与 L0/L1 正交：

| 层 | GEO2 实现 | 本期动作 |
|---|---|---|
| L0 情景 | `AgentMessageORM`（v0.4 已交付） | **不变** |
| L1 语义 | `KnowledgeBase + chunks + documents + bases`（v0.1-5 已交付） | **不变** |
| L2 偏好 | `AgentMemoryORM`（本期新增） | **新加** |

### 3.2 后端新增/改动模块

```
backend/app/
├── core/
│   └── config.py                          # 改: +1 setting
├── api/
│   ├── deps.py                            # 新: device_id_header 依赖
│   ├── agent_chat.py                      # 改: 接 deps + 传参给 react_loop
│   └── diagnosis.py                       # 不动（get_session 已在）
├── models/
│   └── orm_v04.py                         # 改: 新增 AgentMemoryORM 类
├── repositories/
│   └── memory_repo.py                     # 新: MemoryRepository
├── domain/agent/
│   ├── react_loop.py                      # 改: 接 scope + 注入 + extract
│   └── memory.py                          # 新: MemoryService (7 函数)
└── tests/
    ├── conftest.py                        # 不动（Base.metadata 自动建表）
    ├── test_device_header.py              # 新（5 cases）
    ├── test_memory_repo.py                # 新（7 cases）
    ├── test_memory_service.py             # 新（22 cases，含 mock LLM）
    ├── test_react_loop_memory_integration.py  # 新（5 cases）
    └── test_e2e_v04.py                    # 改（+device_id=None 断言）

backend/
└── (无 alembic) — init_db() 自动 create_all
```

### 3.3 前端新增/改动模块

```
frontend/src/
├── lib/
│   └── deviceId.ts                        # 新: 生成/读取 device_id
├── api/
│   └── client.ts                          # 改: 3 处加 X-Device-Id header
└── tests/lib/
    └── deviceId.test.ts                   # 新（4 cases）
```

### 3.4 关键设计原则

| 原则 | 选择 | 理由 |
|---|---|---|
| 架构来源 | 直接 port s09 函数结构 | s09 已经是抽象示范,只换存储后端 |
| 存储 | SQLite `AgentMemoryORM` | 复用现有 `Base.metadata.create_all()` 模式,无 Alembic |
| Trigger 模型 | 后台任务 fire-and-forget | turn_complete 后 `asyncio.create_task`,tracked in module-level set 防 GC |
| scope key | `device_id`,缺失则 fallback `"anon:<session_id>"` | 单 key 简化查询;fallback 保证匿名场景也有 scope |
| 注入位置 | index 拼 system + relevant 内容拼 user turn（per s09） | 索引可被 prompt cache 缓存,relevant 不破坏 cache 命中 |
| 安全 | 非法/缺失 header 静默 None | 不抛 422 容错,degrade 到 anon 行为 |
| 测试框架 | 单测 + mock LLM（同 v0.5 模式） | 沙箱无外网,真 E2E 测 P2+ |

## 4. 数据模型

### 4.1 `AgentMemoryORM`

新增在 `backend/app/models/orm_v04.py`（agent 域就近）

```python
class AgentMemoryORM(Base):
    __tablename__ = "agent_memories"

    id: Mapped[str] = mapped_column(
        String, primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    scope: Mapped[str] = mapped_column(String, index=True)
    name: Mapped[str] = mapped_column(String)
    description: Mapped[str] = mapped_column(String)
    type: Mapped[str] = mapped_column(String)
    body_md: Mapped[str] = mapped_column(Text)
    session_id: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), default=_utcnow,
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), default=_utcnow, onupdate=_utcnow,
    )

    __table_args__ = (
        UniqueConstraint("scope", "name", name="uq_agent_memories_scope_name"),
        Index("idx_agent_memories_scope_mtime", "scope", "updated_at"),
    )
```

字段对照 s09：

| s09 fs 文件 | GEO2 ORM 列 |
|---|---|
| 文件名（file.md） | `id`（UUID） |
| YAML `name` | `name` |
| YAML `description` | `description` |
| YAML `type` | `type` |
| body markdown | `body_md` |
| MEMORY.md index | 实时从 DB 计算（无持久化） |
| （无） | `scope`（新,替代 fs 隔离） |
| （无） | `session_id`（来源追溯） |
| 文件 mtime | `updated_at` |

### 4.2 四类记忆（GEO2 中具体含义）

| type | GEO2 中是什么 | 示例 |
|---|---|---|
| `user` | 用户偏好 | "用户偏好中文回复,英文术语保留" |
| `feedback` | 做事方式约束 | "不要 mock 数据库,要走真路径" |
| `project` | 项目/品牌背景 | "北北云吞是潮汕口味,主打堂食" |
| `reference` | 外部指针 | "pipeline bug 在 Linear INGEST-234" |

## 5. 接口规范

### 5.1 后端依赖

```python
# backend/app/api/deps.py
from fastapi import Header
import uuid

async def device_id_header(
    x_device_id: str | None = Header(default=None, alias="X-Device-Id"),
) -> str | None:
    """读 X-Device-Id,UUID 校验,非法/缺失返回 None（不抛 422）。"""
    if not x_device_id:
        return None
    try:
        uuid.UUID(x_device_id)
        return x_device_id
    except (ValueError, AttributeError):
        return None
```

### 5.2 `run_agent_turn` 新签名

```python
async def run_agent_turn(
    session_id: str,
    user_message: str,
    device_id: str | None = None,  # 新: 来自 X-Device-Id header
) -> AsyncIterator[dict]: ...
```

`run_agent_turn_from_checkpoint` 同样加 `device_id: str | None = None`。

### 5.3 `MemoryService` 7 函数（照搬 s09）

| s09 函数 | GEO2 命名 | 返回 | LLM 调用? |
|---|---|---|---|
| `write_memory_file` | `write_memory(name, scope, type, desc, body, session_id)` | `dict(id)` | 否 |
| `read_memory_index` | `read_memory_index(scope)` | `str` | 否 |
| `read_memory_file` | `read_memory(memory_id)` | `dict \| None` | 否 |
| `list_memory_files` | `list_memories(scope)` | `list[dict]` | 否 |
| `select_relevant_memories` | `select_relevant(scope, messages, k=5)` | `list[dict]` | **是**（失败降级关键词） |
| `load_memories` | `load_relevant_memories(scope, messages)` | `str(prepend block)` | **是**（嵌套） |
| `extract_memories` | `extract(scope, messages, session_id)` | `int(count)` | **是** |
| `consolidate_memories` | `consolidate(scope)` | `int(new_count)` | **是**（阈值触发） |

`build_memory_segment(scope)` 拼 `AGENT_SYSTEM_PROMPT` 用的索引段（无 LLM）。

### 5.4 Settings

```python
# config.py 新增
memory_consolidate_threshold: int = 50  # 行数 ≥ 此值触发 consolidate
```

## 6. 注入与提取机制

### 6.1 注入

**一次性,在 user turn 开头算**:

```python
memory_block = await memory_service.load_relevant_memories(
    scope=scope_key, messages=history,
)
# memory_block 是空字符串 or "<relevant_memories>...</relevant_memories>"
```

**每次 LLM 调用前合入 user 消息**:

```python
def _apply_memory_prepend(messages, prepend):
    if not prepend: return messages
    out = []
    for m in messages:
        if m.get("role") == "user" and m.get("content"):
            out.append({**m, "content": prepend + "\n\n" + m["content"]})
        else:
            out.append(m)
    return out
```

为什么拼 user 不拼 system：保留 system cacheable；per s09 design choice。

### 6.2 提取

**在 `turn_complete` yield 之前**,fire-and-forget:

```python
# 模块顶部
_PENDING_EXTRACTS: set[asyncio.Task] = set()

# 在 yield turn_complete 之前
task = asyncio.create_task(
    _do_extract_after_turn(device_id, session_id, history)
)
_PENDING_EXTRACTS.add(task)
task.add_done_callback(_PENDING_EXTRACTS.discard)

yield {"event": "turn_complete"}
```

两条 yield turn_complete 路径（`run_agent_turn` + `run_agent_turn_from_checkpoint`）都加同一段。

`scope_key` 计算:

```python
def scope_key(device_id: str | None, session_id: str) -> str:
    return device_id if device_id else f"anon:{session_id}"
```

## 7. 文件地图

[见 §3.2 / §3.3 树状列表]

## 8. 错误处理

| 场景 | 行为 |
|---|---|
| header 缺失/非法 UUID | 静默 None,fallback `anon:<session_id>`,extract 仍可写 |
| LLM side-query 失败（select_relevant） | 降级关键词匹配;再降级返回 `[]`,跳过 prepend |
| LLM extract 失败 | catch + log,不影响 turn 响应 |
| LLM consolidate 失败 | catch + log,下轮再触发 |
| 写入 body_md > 字段上限 | 不限（SQLite Text 无上限） |
| test 时 extract 是 fire-and-forget | 模块级 `_PENDING_EXTRACTS` set 防 GC;测试起始 `_PENDING_EXTRACTS.clear()` |

## 9. 测试

| 层 | 文件 | 用例 |
|---|---|---|
| Frontend util | `deviceId.test.ts` | 4 cases：v4 生成 / 持久化返回值 / cached 复用 / 无 window fallback |
| Frontend client | `client.test.ts`（新加） | 3 cases：X-Device-Id 在 request wrapper + 2 SSE 入口 |
| Backend dep | `test_device_header.py` | 5 cases：合法 UUID / 非法 / 空串 / 缺失 / 附加字符 |
| Backend repo | `test_memory_repo.py` | 7 cases：CRUD + list_by_scope + count_by_scope + replace_all_bulk 范围隔离 |
| Backend service | `test_memory_service.py` | 22 cases：write_memory + index + select_relevant (LLM + 关键词降级) + load + extract (dedup, invalid json, session_id) + consolidate (threshold gating via extract + invalid response) + Settings |
| Backend integration | `test_react_loop_memory_integration.py` | 5 cases：system index / user turn prepend / fire-and-forget extract / no-device-id fallback / scope isolation |
| Backend 已有测试 | `test_e2e_v04.py` + 全量回归（204+ passed 基线 + 32 新增 = 236+） | |

mock LLM 模板（沿用 v0.5 模式）：
```python
with patch("app.domain.agent.memory.LLMClient") as MockLLM:
    inst = MockLLM.return_value
    inst.simple_chat = AsyncMock(side_effect=[...])  # 喂 JSON 字符串
```

## 10. 风险与未做

| 项 | 状态 | 备注 |
|---|---|---|
| L2 prompt 注入攻击（用户在对话中"记住 system prompt ..."会被蒸馏） | 未做 | 用户明确否决注入过滤 |
| 跨设备 memory 串了 | 未做 | localStorage 是浏览器级,清数据才能跨设备,符合设计 |
| 大量 memory 拖累 select_relevant LLM 调用 | 单次 ~50 行上下文 OK;若膨胀,后续加 truncation | v2+ |
| 离线 / 异步 extract 失败无重试 | catch + log,不重试 | v2+ 加 retry queue |
| scope fallback `anon:<session_id>` 下匿名用户共享同一 scope | 设计权衡 | 实际场景:多会话的"清缓存"用户会感觉失效 |

## 11. 决策日志

| 决策 | 选项 | 选择 | 理由 |
|---|---|---|---|
| 存储后端 | fs vs SQLite | SQLite | 复用现有 init_db;多进程/容器部署友好;不引 Alembic |
| trigger 时机 | inline vs fire-and-forget | fire-and-forget（`asyncio.create_task`） | 不阻塞 SSE;失败不拖累 turn |
| scope key | session_id vs device_id vs 双 key | device_id（单 key） | 实现最简;session_id 写入 body 注释做来源追溯 |
| header 校验 | UUID 严格校验 vs 任意字符串 | 严格（UUID） | 防止任意字符串污染 scope 字段 |
| header 缺失行为 | 抛 422 vs 静默 None | 静默 None | 容错优先;不影响主路径 |
| 注入位置 | system prompt vs user turn | system 拼索引 + user 拼 relevant | 索引 cacheable,relevant per s09 design |
| LLM side-query 失败 | 报错 vs 关键词降级 | 关键词降级 | 沿用 s09 |
| agent tool 暴露 | 是 vs 否 | 否 | s09 默认配置;用户 7-13 拍板 |
| 整理触发 | 行数 vs 多门控 | 行数 ≥ 50 | 用户 7-13 拍板 |
| 跨测试 task 残留 | .clear vs await drain vs 忽略 | `.clear()` | pytest-asyncio 每测试新 loop,残留 task 跨 loop await 失败;clear 最稳 |

## 12. 退出标准

- [x] frontend 单测全 pass（含 87+ 基线 + 7 个新增）
- [x] backend 单测 442+ 全 pass（+32 个新加,合计 ~470+）
- [x] 手动 e2e：（注：沙箱无外网,不实际跑,SPEC 写明路径）
- [x] `npm run typecheck` 过（`tsc --noEmit` 已有 lint script 路径）
- [x] 已有 v0.6 P0-P1.5 功能无回归（诊断 / KB / Agent 5 工具 / 文章详情 + 复制 / 下载）
- [x] L0（`AgentMessageORM`）和 L1（`KnowledgeBase`）行为不变
- [x] 提交历史清晰,7 个 commit（每个 Task 一个,可选 squash）
