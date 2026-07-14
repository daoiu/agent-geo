# HITL 事件 Schema 文档 (v0.7+ / P1#33 / Task 34)

> 关联：[app/domain/hitl_schemas.py](../backend/app/domain/hitl_schemas.py) — Pydantic 模型源

GEO2 的 ReAct 循环在三种 HITL（Human-in-the-Loop）场景下会 yield SSE 事件暂停循环。本文档定义事件 payload 契约，前端订阅和后端校验都以此为准。

---

## 1. 三类 HITL 总览

| kind | 触发场景 | event 名 | 用户操作 |
| --- | --- | --- | --- |
| `decision` | 写类工具需用户授权（如 generate_article 实时预览） | `human_confirmation_required` | approve / reject (+ reason) |
| `input` | 工具需要补充参数（如 search_local 缺城市名） | `input_required` | 提供 inputs 字段 |
| `progress_confirm` | 长任务中途报告进度 | `progress_confirm` | 继续 / 取消 |

---

## 2. 事件 Payload 契约

### 2.1 DecisionRequiredEvent

```json
{
  "event": "human_confirmation_required",
  "kind": "decision",
  "message_id": "msg-uuid-1",
  "tool_name": "generate_article",
  "arguments": {
    "title": "小米 14 评测",
    "target_length": 800
  }
}
```

字段：
- `event` (固定): `"human_confirmation_required"` (与 v0.4 老事件名兼容)
- `kind` (固定): `"decision"`
- `message_id`: 已落库的"待确认"消息 ID
- `tool_name`: 触发 HITL 的工具名
- `arguments`: 工具调用参数

### 2.2 InputRequiredEvent

```json
{
  "event": "input_required",
  "kind": "input",
  "message_id": "msg-uuid-2",
  "tool_name": "search_local",
  "arguments": { "query": "天气" },
  "input_schema": {
    "fields": [
      { "name": "city", "type": "string", "required": true }
    ]
  },
  "prompt": "请告诉我查询哪个城市的天气？"
}
```

额外字段：
- `input_schema`: 描述用户需提供哪些字段（JSON Schema 风格）
- `prompt`: 给用户的提示语

### 2.3 ProgressConfirmEvent

```json
{
  "event": "progress_confirm",
  "kind": "progress_confirm",
  "message_id": "msg-uuid-3",
  "tool_name": "batch_generate",
  "arguments": { "task_id": "task-99", "total": 100 },
  "progress_pct": 42.5,
  "eta_seconds": 120
}
```

额外字段：
- `progress_pct`: 0-100 进度百分比
- `eta_seconds`: 预计剩余秒数

---

## 3. 用户响应 Schema

```json
{
  "approved": true,
  "reason": "好的，同意生成",
  "inputs": { "city": "北京" }
}
```

字段：
- `approved` (bool): true=同意/继续, false=取消/拒绝
- `reason` (str | null): 可选说明（影响后续 LLM 上下文）
- `inputs` (dict | null): 补充输入（InputRequiredEvent 专用）

---

## 4. 完整事件流示例

```
client→server: POST /api/agent/sessions/{sid}/messages  {"query": "生成小米14评测"}
server→client: event: tool_call
              data: {"name": "generate_article", "args": {...}}

server→client: event: human_confirmation_required
              data: {"event": "human_confirmation_required",
                     "kind": "decision",
                     "message_id": "msg-1",
                     "tool_name": "generate_article",
                     "arguments": {...}}

(用户确认)
client→server: POST /api/agent/sessions/{sid}/messages/{msg_id}/confirm  {"approved": true}

server→client: event: tool_call_result
              data: {...}

server→client: event: turn_complete
```

---

## 5. JSON Schema 导出

`HITL_EVENT_SCHEMAS` 字典（按 kind 索引）支持 Pydantic 的 `model_json_schema()` 输出标准 JSON Schema，可用于：
- 前端 TypeScript 类型自动生成（openapi-typescript 等）
- OpenAPI 文档展示
- 跨语言契约验证

```python
from app.domain.hitl_schemas import HITL_EVENT_SCHEMAS
schema = HITL_EVENT_SCHEMAS["decision"].model_json_schema()
```

---

## 6. 版本兼容性

- v0.4 起：仅 `human_confirmation_required` 事件（kind=decision）
- v0.7+ (本版本)：新增 `input_required` / `progress_confirm` 两种事件
- v0.4 老客户端：忽略未知事件名，继续订阅 `human_confirmation_required` 即可（kind 字段向后兼容）