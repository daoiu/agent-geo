# 04. 权限策略

> 面试官视角：本维度在 GEO2 的现状、评分、讲述建议、改进路径。

## 1. 维度定义

高风险操作的鉴权、确认流、审计。包括：危险工具的用户确认、权限分级、审计日志、声明式策略、自动化测试覆盖。

依据：[`00-learning-summary.md` §6.4](./00-learning-summary.md)

## 2. 评分标准（0-5 分制）

| 分数 | 含义 | 触发条件 |
| --- | --- | --- |
| 0 | 缺失 | 无任何权限控制 |
| 1 | 雏形 | 仅有注释/意向 |
| 2 | 基础 | 有确认流但不完整 |
| 3 | 达标 | 危险工具有用户确认 |
| 4 | 良好 | 权限分级、有审计日志 |
| 5 | 卓越 | 策略可声明式配置、有自动化测试覆盖 |

## 3. GEO2 现状调研

### 3.1 HumanConfirmation 机制（强项）

来源：[`exceptions.py` L97–L112](./../backend/app/domain/exceptions.py)

```python
class HumanConfirmationRequired(DomainError):
    """写类工具需要人工确认后才能继续执行。

    由 ToolExecutor 在执行 generate_article 等写类工具时抛出，
    携带 message_id（已落库的"待确认"消息）、tool_name 和 arguments，
    ReAct 循环捕获后 yield SSE 事件 human_confirmation_required 并暂停。
    """

    def __init__(self, message_id: str, tool_name: str, arguments: dict) -> None:
        self.message_id = message_id
        self.tool_name = tool_name
        self.arguments = arguments
```

**优点**：

- ✓ 携带完整上下文（message_id / tool_name / arguments）—— 用户确认时无需重新传
- ✓ DomainError 子类（领域异常层次清晰）
- ✓ 写类工具统一抛该异常（ToolExecutor 层）

### 3.2 API 端点 confirm_action（强项）

来源：[`agent_chat.py` L74–L127](./../backend/app/api/agent_chat.py)

```python
@router.post(
    "/sessions/{session_id}/messages/{message_id}/confirm",
    response_model=None,
)
async def confirm_action(...):
    repo = AgentRepository(session)
    msg = await repo.get_message(message_id)
    if msg is None:
        raise HTTPException(status_code=404, detail="message not found")
    if msg.session_id != session_id:
        raise HTTPException(status_code=404, detail="message does not belong to this session")
    if not msg.pending_confirmation:
        raise HTTPException(status_code=409, detail="message is not pending confirmation")

    if not body.approved:
        await repo.confirm_message(message_id, approved=False)
        await repo.create_message(session_id=session_id, role="user", content="取消")
        await repo.create_message(session_id=session_id, role="assistant", content="好的，已取消。")
        return Response(...)

    await repo.confirm_message(message_id, approved=True)
    async def event_generator():
        async for event in run_agent_turn_from_checkpoint(...):
            ...
```

**优点**：

- ✓ 严格校验（404 / 409 状态码清晰）
- ✓ 跨 session 验证（msg.session_id != session_id 阻止跨用户操作）
- ✓ approved=False 写"取消"消息（用户决策可追溯）
- ✓ approved=True 走断点续跑流

### 3.3 DB 持久化与审计

来源：[`orm_v04.py` L52](./../backend/app/models/orm_v04.py)

```python
pending_confirmation: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
```

来源：[`agent_repo.py` L92–L102](./../backend/app/repositories/agent_repo.py)

```python
async def create_message(
    ...,
    pending_confirmation: bool = False,
    ...
):
    ...
    pending_confirmation=1 if pending_confirmation else 0,
```

**优点**：

- ✓ 持久化 pending_confirmation（重启可恢复）
- ✓ 0/1 int 而非 bool（兼容旧 DB schema）
- ✓ 每条消息独立标记（可单独审计）

### 3.4 权限分级（v0.6 P1.6 演进）

| 工具 | 权限级别 | 处理 |
| --- | --- | --- |
| diagnose_brand | 读 | 直接执行 |
| search_knowledge | 读 | 直接执行 |
| list_knowledge_bases | 读 | 直接执行 |
| generate_article | 写（默认后台） | v0.6 P1.6+ 默认 article_count=1，不需确认 |
| create_generation_task | 写（不需确认） | 直接落 v0.2 tasks 表 + worker |

**写入操作的层级**：

- generate_article 走"实时预览"路径时需 HumanConfirmation（保留 v0.4 老路径，但默认关闭）
- generate_article 走"批量任务"路径时不需确认（v0.6 P1.6+ 默认）
- create_generation_task 直接后台任务，不需确认

**设计取舍**：写入操作的"危险程度"按业务流而非工具本身分级（批量任务由前端审核 UI 处理，单篇预览需会话内确认）。

### 3.5 其他安全机制

来源：[`ssrf.py` L29–L53](./../backend/app/domain/security/ssrf.py)

```python
def _allow_private_ips() -> bool:
    ...

def _allow_multicast() -> bool:
    ...
```

**SSRF 防护**：诊断工具爬虫时阻止私有 IP / 多播地址（防止 agent 触发内部探测）。

来源：[`main.py` L49–L52](./../backend/app/main.py)

```python
allow_origins=["http://localhost:5173", "*"],
allow_credentials=True,
allow_methods=["*"],
allow_headers=["*"],
```

**CORS 配置**：开发模式允许 localhost:5173（前端开发服务器），生产应严格化。

### 3.6 权限测试覆盖

来源：[`backend/tests/`](./../backend/tests/) —— 没有专门的 `test_permission.py` 或 `test_confirm_action.py`。

确认机制覆盖在 `test_api_agent_chat.py`（API 集成测试）和 `test_agent_tool_executor_create_task.py`（create_generation_task 不需确认的测试）。

**缺口**：HumanConfirmation 路径（v0.4 老路径）的自动化测试覆盖较弱，因为该路径"暂未启用"（见 02-tool-boundary）。

## 4. 评分与理由

**评分：4 / 5（良好）**

| 维度 | 现状 | 评分贡献 |
| --- | --- | --- |
| 危险工具确认 | ✓ HumanConfirmationRequired 异常驱动 | +1 |
| 权限分级 | ✓ 读/写 + 批量/单篇 | +1 |
| 审计日志 | ✓ DB 持久化 + metrics | +1 |
| 跨 session 校验 | ✓ 端点层校验 | +0.5 |
| 声明式策略 | ✗ hard-coded 在 tool_executor.py | - |
| 自动化测试 | 部分（API 集成测试覆盖，但无专项） | +0.5 |

**关键证据**：

- 强项：HumanConfirmation 设计完整（异常 + 端点 + DB + 审计）
- 弱项：策略 hard-coded、HumanConfirmation 路径测试弱

**与行业标准差距**：

- 缺声明式策略：未来添加工具时需修改两处（ToolExecutor + ORM 标记）
- 缺专项测试：HumanConfirmation 路径是安全关键，需要覆盖

## 5. 面试讲点

### 30 秒版本

> 写类工具抛 HumanConfirmationRequired 暂停 ReAct 循环；API confirm 端点支持 approve/reject；DB 持久化 pending_confirmation；批量任务（v0.6+）走后台审核流。

### 2 分钟版本

1. **核心机制**：
   - HumanConfirmationRequired 异常（携带 message_id / tool_name / arguments）
   - ReAct 循环捕获后 yield human_confirmation_required 事件
   - 前端弹窗 → 调 confirm 端点
2. **API confirm_action**：
   - 严格校验（404 / 409 状态码）
   - 跨 session 校验（阻止越权）
   - approved=False 写"取消"消息（用户决策可追溯）
3. **DB 持久化**：pending_confirmation int 0/1（兼容旧 schema）
4. **设计取舍**：v0.6 P1.6+ 默认走后台任务，前端审核 UI 处理；HumanConfirmation 路径保留为"实时预览"出口

### 追问预判

| 追问 | 回答要点 |
| --- | --- |
| 跨用户操作如何防？ | 端点校验 msg.session_id != session_id 直接 404 |
| approve=False 后能重新 approve 吗？ | 否，confirm_message 会清掉 pending_confirmation（需重新调 Agent） |
| 批量任务为什么不需确认？ | 落 v0.2 tasks 表，由前端审核 UI 处理；避免阻塞对话 |
| 有没有"自动拒绝超时"？ | 目前没有（**改进候选**） |
| SSRF 防护在哪？ | security/ssrf.py 阻止私有 IP / 多播地址 |

## 6. 改进建议

| 优先级 | 改进项 | 关联 |
| --- | --- | --- |
| P1 | 声明式权限策略（per-tool confirmation_required: bool 配置） | 见 `99-improvement-plan.md` |
| P1 | HumanConfirmation 路径专项测试（覆盖 approve/reject 流程） | 见 `99-improvement-plan.md` |
| P2 | 自动拒绝超时（pending > N 秒自动取消） | 见 `99-improvement-plan.md` |
| P2 | 权限操作审计日志独立表（permission_audit） | 见 `99-improvement-plan.md` |
| P2 | CORS 生产严格化（移除 `"*"` 通配） | 见 `99-improvement-plan.md` |