"""v0.6+ P1#25（Task 26）：pending_confirmation 超时自动取消。

场景：用户发起需要确认的工具调用后离开,pending_confirmation 消息一直挂起。
设计:定时任务(或每次 session 启动时)扫描 pending 消息,
对超过阈值的标记 resolved + 追加"user_timeout" user 消息,
下次 LLM turn 会看到这条消息,做出合理响应(放弃 / 提示用户)。

可被 main.py lifespan 或后台 scheduler 周期调用。
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone

import structlog

from app.core.db import get_session_factory
from app.repositories.agent_repo import AgentRepository


logger = structlog.get_logger()


def auto_cancel_pending_messages(timeout_minutes: int = 5) -> int:
    """扫描并自动取消超时的 pending_confirmation 消息。

    Args:
        timeout_minutes: 超时阈值(分钟),默认 5

    Returns:
        实际取消的消息数量(int)

    行为:
    - 找出 created_at < now() - timeout_minutes 且 pending_confirmation=1 的消息
    - 标记 resolved(pending_confirmation=0)
    - 追加 "user_timeout" user 消息(便于 LLM 后续 turn 看到)
    - 不抛异常(单条失败不影响其他)
    """
    return asyncio.run(_async_auto_cancel(timeout_minutes))


async def _async_auto_cancel(timeout_minutes: int) -> int:
    """async 内部实现,使用 get_session_factory 拉 session。"""
    factory = get_session_factory()
    threshold = datetime.now(timezone.utc) - timedelta(minutes=timeout_minutes)

    cancelled = 0
    async with factory() as session:
        repo = AgentRepository(session)
        # 拉所有 pending 消息(v0.6 P1.6+ 实际数据量小,内存扫可接受)
        from sqlalchemy import select, update
        from app.models.orm_v04 import AgentMessageORM

        result = await session.execute(
            select(AgentMessageORM).where(AgentMessageORM.pending_confirmation == 1)
        )
        pending_msgs = result.scalars().all()

        for msg in pending_msgs:
            # 比较 created_at(可能是 naive datetime,统一转 aware)
            created = msg.created_at
            if created.tzinfo is None:
                created = created.replace(tzinfo=timezone.utc)
            if created > threshold:
                continue  # 未超时

            try:
                # 标记 resolved
                await repo.confirm_message(msg.id, approved=False)
                # 追加 user_timeout 消息
                await repo.create_message(
                    session_id=msg.session_id,
                    role="user",
                    content=f"[系统] 该消息已超时未响应(>{timeout_minutes}分钟),自动取消。",
                )
                logger.info(
                    "pending_message_auto_cancelled",
                    message_id=msg.id,
                    session_id=msg.session_id,
                    age_minutes=int((datetime.now(timezone.utc) - created).total_seconds() / 60),
                )
                cancelled += 1
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "pending_message_auto_cancel_failed",
                    message_id=msg.id,
                    error=str(exc),
                )
                continue

    return cancelled