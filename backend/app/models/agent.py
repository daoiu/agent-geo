"""Pydantic models for v0.4 agent API."""
from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class AgentMessageRole(str, Enum):
    """消息角色枚举。"""

    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"
    SYSTEM = "system"


class AgentSession(BaseModel):
    """单个 session 摘要（列表用）。"""

    model_config = ConfigDict(from_attributes=True)

    id: str
    title: str
    created_at: datetime
    updated_at: datetime


class AgentMessage(BaseModel):
    """单条消息（含 tool_calls / pending_confirmation）。"""

    model_config = ConfigDict(from_attributes=True)

    id: str
    session_id: str
    role: AgentMessageRole
    content: str | None
    tool_calls: list[dict] | None
    tool_call_id: str | None
    pending_confirmation: bool
    created_at: datetime


class AgentSessionDetail(BaseModel):
    """Session + 完整消息历史。"""

    id: str
    title: str
    created_at: datetime
    updated_at: datetime
    messages: list[AgentMessage]


class CreateSessionRequest(BaseModel):
    """创建 session 请求体。"""

    title: str | None = Field(None, max_length=200)


class UpdateSessionRequest(BaseModel):
    """更新 session 标题请求体。"""

    title: str = Field(..., min_length=1, max_length=200)