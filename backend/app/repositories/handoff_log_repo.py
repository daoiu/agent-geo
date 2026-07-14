"""HandoffLogRepository:HandoffLogORM 的数据访问层(纪律 1 + 纪律 5)。

纪律 1 (幂等键): check_idempotency 查询窗口内同 handoff_id 的成功结果
纪律 5 (成本归因): insert 写入 + aggregate_by_specialist 按 specialist 聚合
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.agent.handoff import HandoffRequest, HandoffResult
from app.models.orm_v05 import HandoffLogORM


class HandoffLogRepository:
    """HandoffLog 表的数据访问。"""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def insert(self, request: HandoffRequest, result: HandoffResult) -> None:
        """写入一条 handoff 日志(纪律 5 成本归因)。"""
        log = HandoffLogORM(
            id=request.handoff_id,
            specialist=request.specialist,
            task_id=request.task_id,
            session_id=request.session_id,
            started_at=request.started_at,
            duration_ms=result.duration_ms,
            status=result.status,
            error=result.error,
            prompt_tokens=result.token_usage.get("prompt_tokens", 0),
            completion_tokens=result.token_usage.get("completion_tokens", 0),
            total_tokens=result.token_usage.get("total_tokens", 0),
        )
        self.session.add(log)

    async def check_idempotency(
        self, handoff_id: str, window_hours: int = 24
    ) -> HandoffResult | None:
        """纪律 1:查窗口内同 handoff_id 的成功结果(失败不算幂等,允许重试)。"""
        cutoff = datetime.now(timezone.utc) - timedelta(hours=window_hours)
        stmt = select(HandoffLogORM).where(
            HandoffLogORM.id == handoff_id,
            HandoffLogORM.status == "success",
            HandoffLogORM.started_at >= cutoff,
        )
        result = await self.session.execute(stmt)
        log = result.scalar_one_or_none()
        if log is None:
            return None
        return HandoffResult(
            handoff_id=log.id,
            status=log.status,
            result=None,  # 幂等命中不重放 result,只标记完成
            error=None,
            duration_ms=log.duration_ms or 0,
            token_usage={
                "prompt_tokens": log.prompt_tokens,
                "completion_tokens": log.completion_tokens,
                "total_tokens": log.total_tokens,
            },
        )

    async def aggregate_by_specialist(self, days: int = 7) -> list[dict]:
        """纪律 5:按 specialist + status 聚合,供成本 dashboard。"""
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        stmt = (
            select(
                HandoffLogORM.specialist,
                HandoffLogORM.status,
                func.count(HandoffLogORM.id).label("count"),
                func.sum(HandoffLogORM.total_tokens).label("total_tokens"),
            )
            .where(HandoffLogORM.started_at >= cutoff)
            .group_by(HandoffLogORM.specialist, HandoffLogORM.status)
        )
        result = await self.session.execute(stmt)
        rows = result.all()
        # 转成 dict 列表,聚合结果按 specialist 合并
        agg: dict[str, dict] = {}
        for row in rows:
            specialist = row.specialist
            if specialist not in agg:
                agg[specialist] = {
                    "specialist": specialist,
                    "success_count": 0,
                    "failed_count": 0,
                    "timeout_count": 0,
                    "cancelled_count": 0,
                    "total_tokens": 0,
                }
            key = f"{row.status}_count"
            if key in agg[specialist]:
                agg[specialist][key] = row.count
            agg[specialist]["total_tokens"] += row.total_tokens or 0
        return list(agg.values())
