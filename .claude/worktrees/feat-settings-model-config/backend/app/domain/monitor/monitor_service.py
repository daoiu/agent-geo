"""Orchestrates a single monitor run: query LLM, save snapshot, check threshold."""
from __future__ import annotations

import json
import structlog
from datetime import datetime, timezone

from app.core.config import get_settings
from app.core.db import get_session_factory
from app.domain.llm_client import LLMClient
from app.repositories.monitor_repo import MonitorRepository

logger = structlog.get_logger()


async def execute_monitor_run(monitor_task_id: str) -> None:
    """Execute one monitor snapshot. Reuses v0.1's LLMClient."""
    factory = get_session_factory()
    settings = get_settings()
    async with factory() as session:
        repo = MonitorRepository(session)
        task = await repo.get_monitor_task(monitor_task_id)
        if task is None or not task.is_active:
            return

        await repo.update_monitor_last_run(monitor_task_id, datetime.now(timezone.utc))

        try:
            llm = LLMClient(settings)
            mentions = await llm.query_mentions(
                brand=task.brand,
                industry=task.industry,
                questions=json.loads(task.target_questions),
                providers=json.loads(task.providers),
            )

            valid = [m for m in mentions if m.error is None]
            mentioned = [m for m in valid if m.brand_mentioned]
            rate = len(mentioned) / len(valid) if valid else 0.0
            avg_pos = (
                sum(m.mention_position for m in mentioned if m.mention_position) / len(mentioned)
                if mentioned else None
            )

            snapshot_id = await repo.create_snapshot(
                monitor_task_id=monitor_task_id,
                run_at=datetime.now(timezone.utc),
                mention_rate=rate,
                mention_count=len(mentioned),
                total_samples=len(valid),
                avg_position=avg_pos,
                details=[vars(m) for m in mentions],
            )

            logger.info(
                "monitor_run_done",
                task_id=monitor_task_id,
                rate=rate,
                mentioned=len(mentioned),
                total=len(valid),
            )

            if task.notify_email:
                await check_and_notify_change(task, current_rate=rate, snapshot_id=snapshot_id)
        except Exception as e:  # noqa: BLE001
            logger.exception("monitor_run_failed", task_id=monitor_task_id)
            await repo.create_snapshot(
                monitor_task_id=monitor_task_id,
                run_at=datetime.now(timezone.utc),
                mention_rate=0.0,
                mention_count=0,
                total_samples=0,
                avg_position=None,
                details=[],
                error_message=f"{type(e).__name__}: {e}",
            )


async def check_and_notify_change(task, current_rate: float, snapshot_id: str) -> None:
    """Compare current snapshot to previous; send email if change > threshold."""
    factory = get_session_factory()
    async with factory() as session:
        repo = MonitorRepository(session)
        previous = await repo.get_previous_snapshot(task.id, before_id=snapshot_id)
    if previous is None:
        return
    if not task.notify_email:
        return

    delta = abs(current_rate - previous.mention_rate)
    if delta < task.change_threshold:
        return

    direction = "上升" if current_rate > previous.mention_rate else "下降"
    subject = f"[GEO 监测] {task.name} - 提及率{direction} {delta*100:.1f}%"
    body = f"""品牌：{task.brand}
当前提及率：{current_rate * 100:.1f}%
上次提及率：{previous.mention_rate * 100:.1f}%
变化：{direction} {delta * 100:.1f}%（阈值 {task.change_threshold * 100:.0f}%）
执行时间：{datetime.now(timezone.utc).isoformat()}

查看详情：http://localhost:5173/monitors/{task.id}
"""
    try:
        from app.domain.notification.notification_service import send_email
        await send_email(to=task.notify_email, subject=subject, body=body)
    except Exception as e:  # noqa: BLE001
        logger.warning("notification_email_failed", error=str(e))
