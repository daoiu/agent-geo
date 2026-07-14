"""HITL 事件 schema(P1#33 / Task 34)。

为三种 HITL 类型提供 Pydantic 模型,用于:
- SSE 事件 payload 类型校验(react_loop yield 时校验)
- JSON Schema 导出(供前端 codegen / OpenAPI 文档)
- API 请求/响应校验

字段命名规范:
- event: SSE 事件名(给前端订阅用)
- kind: HITL 类型判别式(decision/input/progress_confirm)
- message_id: 已落库的"待确认"消息 ID
- tool_name: 触发 HITL 的工具名
- arguments: 工具调用的参数(决策/输入类需要原样回传)

类型特定字段:
- InputRequiredEvent: input_schema + prompt
- ProgressConfirmEvent: progress_pct + eta_seconds
"""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class _BaseHITLEvent(BaseModel):
    """HITL 事件基类,所有子类共享 4 个核心字段。"""

    model_config = ConfigDict(extra="forbid", frozen=False)

    event: str
    kind: str
    message_id: str
    tool_name: str
    arguments: dict[str, Any]


class DecisionRequiredEvent(_BaseHITLEvent):
    """决策类 HITL 事件: 写类工具等待用户 approve / reject。

    event=human_confirmation_required (向前兼容 v0.4 老事件名)
    kind=decision
    """

    event: Literal["human_confirmation_required"] = "human_confirmation_required"
    kind: Literal["decision"] = "decision"


class InputRequiredEvent(_BaseHITLEvent):
    """输入类 HITL 事件: 工具调用需要用户补充参数。

    event=input_required
    kind=input
    extra:
    - input_schema: 描述需要哪些字段(JSON Schema 风格)
    - prompt: 给用户的提示语
    """

    event: Literal["input_required"] = "input_required"
    kind: Literal["input"] = "input"
    input_schema: dict[str, Any] = Field(..., description="需要用户输入的字段 schema")
    prompt: str = Field(..., description="向用户展示的提示语")


class ProgressConfirmEvent(_BaseHITLEvent):
    """进度确认类 HITL 事件: 长任务中途报告进度等待确认。

    event=progress_confirm
    kind=progress_confirm
    extra:
    - progress_pct: 0-100 进度百分比
    - eta_seconds: 预计剩余秒数
    """

    event: Literal["progress_confirm"] = "progress_confirm"
    kind: Literal["progress_confirm"] = "progress_confirm"
    progress_pct: float = Field(..., ge=0.0, le=100.0)
    eta_seconds: float = Field(..., ge=0.0)


# 按 kind 索引,供 react_loop 校验/序列化用
HITL_EVENT_SCHEMAS: dict[str, type[_BaseHITLEvent]] = {
    "decision": DecisionRequiredEvent,
    "input": InputRequiredEvent,
    "progress_confirm": ProgressConfirmEvent,
}


# 用户响应 schema(approve/reject 携带 reason)

class UserHITLResponse(BaseModel):
    """用户对 HITL 事件的响应。

    - approved: True=同意/继续,False=取消/拒绝
    - reason: 可选说明(影响后续 LLM 上下文)
    - inputs: 补充输入(InputRequiredEvent 专用,key/value 对应 input_schema 字段)
    """

    model_config = ConfigDict(extra="forbid")

    approved: bool
    reason: str | None = None
    inputs: dict[str, Any] | None = None


__all__ = [
    "DecisionRequiredEvent",
    "InputRequiredEvent",
    "ProgressConfirmEvent",
    "HITL_EVENT_SCHEMAS",
    "UserHITLResponse",
]