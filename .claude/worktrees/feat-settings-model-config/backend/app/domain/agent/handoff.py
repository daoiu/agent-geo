"""v0.6+ Multi-Agent Handoff 协议:主 Agent → Specialist 的最小契约。

设计要点(对应 spec §3.2 5 条工程纪律):
- HandoffRequest: 5 字段 + 1 payload(specialist 专属入参)
- HandoffResult: 状态机 success / failed / timeout / cancelled
- SpecialistHandoffError: 异常携带 handoff_id,主 Agent catch 时可关联日志

纪律实现位置:
- 纪律 1 (幂等键) 在 handoff_log_repo.check_idempotency 实现
- 纪律 2 (超时) 在 specialist 内部 _execute_with_timeout 实现
- 纪律 3 (状态隔离) 由 specialist 设计本身保证(独立 session + 不持有 ReAct 状态)
- 纪律 4 (失败回退) 在 tool_executor / monitor scheduler 改造时实现
- 纪律 5 (成本归因) 在 handoff_log_repo.insert 实现
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal


SpecialistName = Literal["content_writer", "monitor"]
HandoffStatus = Literal["success", "failed", "timeout", "cancelled"]


@dataclass(frozen=True)
class HandoffRequest:
    """主 Agent → Specialist 的最小契约(不可变)。"""

    handoff_id: str                # 幂等键,UUID4
    specialist: SpecialistName
    task_id: str                   # 主 Agent session 内 task_id
    session_id: str                # 主 Agent session_id
    started_at: datetime
    timeout_seconds: int           # 默认 300 (cw) / 60 (monitor)
    payload: dict


@dataclass
class HandoffResult:
    """Specialist → 主 Agent 的回包。"""

    handoff_id: str
    status: HandoffStatus
    result: dict | None
    error: str | None
    duration_ms: int
    token_usage: dict = field(default_factory=dict)

    def __post_init__(self) -> None:
        """纪律契约: failed / timeout / cancelled 状态必须带 error 描述。"""
        if self.status != "success" and not self.error:
            raise ValueError(f"status={self.status} 时 error 不能为空")


class SpecialistHandoffError(Exception):
    """Specialist 抛出的异常,主 Agent catch 时拿 handoff_id 关联日志。"""

    def __init__(self, message: str, handoff_id: str) -> None:
        super().__init__(message)
        self.handoff_id = handoff_id
