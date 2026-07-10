"""Repository for monitor tasks and mention snapshots."""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.orm_v03 import MentionSnapshotORM, MonitorTaskORM


class MonitorRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    # --- MonitorTask ---

    async def create_monitor_task(
        self,
        name: str,
        brand: str,
        industry: str,
        target_questions: list[str],
        frequency: str,
        providers: list[str],
        notify_email: str | None = None,
        change_threshold: float = 0.15,
    ) -> MonitorTaskORM:
        m = MonitorTaskORM(
            id=str(uuid.uuid4()),
            name=name,
            brand=brand,
            industry=industry,
            target_questions=json.dumps(target_questions, ensure_ascii=False),
            frequency=frequency,
            providers=json.dumps(providers),
            notify_email=notify_email,
            change_threshold=change_threshold,
            is_active=1,
        )
        self.session.add(m)
        await self.session.commit()
        await self.session.refresh(m)
        return m

    async def get_monitor_task(self, id: str) -> MonitorTaskORM | None:
        result = await self.session.execute(
            select(MonitorTaskORM).where(MonitorTaskORM.id == id)
        )
        return result.scalar_one_or_none()

    async def list_monitor_tasks(self) -> list[MonitorTaskORM]:
        result = await self.session.execute(
            select(MonitorTaskORM).order_by(MonitorTaskORM.created_at.desc())
        )
        return list(result.scalars().all())

    async def list_active_monitor_tasks(self) -> list[MonitorTaskORM]:
        result = await self.session.execute(
            select(MonitorTaskORM)
            .where(MonitorTaskORM.is_active == 1)
            .order_by(MonitorTaskORM.created_at.desc())
        )
        return list(result.scalars().all())

    async def update_monitor_task(
        self,
        id: str,
        name: str | None = None,
        brand: str | None = None,
        industry: str | None = None,
        target_questions: list[str] | None = None,
        frequency: str | None = None,
        providers: list[str] | None = None,
        notify_email: str | None = None,
        change_threshold: float | None = None,
        is_active: bool | None = None,
    ) -> None:
        m = await self.get_monitor_task(id)
        if m is None:
            return
        if name is not None:
            m.name = name
        if brand is not None:
            m.brand = brand
        if industry is not None:
            m.industry = industry
        if target_questions is not None:
            m.target_questions = json.dumps(target_questions, ensure_ascii=False)
        if frequency is not None:
            m.frequency = frequency
        if providers is not None:
            m.providers = json.dumps(providers)
        if notify_email is not None:
            m.notify_email = notify_email
        if change_threshold is not None:
            m.change_threshold = change_threshold
        if is_active is not None:
            m.is_active = 1 if is_active else 0
        m.updated_at = datetime.now(timezone.utc)
        await self.session.commit()

    async def update_monitor_last_run(self, id: str, run_at: datetime) -> None:
        m = await self.get_monitor_task(id)
        if m is None:
            return
        m.last_run_at = run_at
        m.updated_at = datetime.now(timezone.utc)
        await self.session.commit()

    async def delete_monitor_task(self, id: str) -> None:
        await self.session.execute(
            delete(MonitorTaskORM).where(MonitorTaskORM.id == id)
        )
        await self.session.commit()

    # --- MentionSnapshot ---

    async def create_snapshot(
        self,
        monitor_task_id: str,
        run_at: datetime,
        mention_rate: float,
        mention_count: int,
        total_samples: int,
        avg_position: float | None,
        details: list[dict],
        error_message: str | None = None,
    ) -> str:
        s = MentionSnapshotORM(
            id=str(uuid.uuid4()),
            monitor_task_id=monitor_task_id,
            run_at=run_at,
            mention_rate=mention_rate,
            mention_count=mention_count,
            total_samples=total_samples,
            avg_position=avg_position,
            details=json.dumps(details, ensure_ascii=False),
            error_message=error_message,
        )
        self.session.add(s)
        await self.session.commit()
        return s.id

    async def get_snapshot(self, id: str) -> MentionSnapshotORM | None:
        result = await self.session.execute(
            select(MentionSnapshotORM).where(MentionSnapshotORM.id == id)
        )
        return result.scalar_one_or_none()

    async def get_previous_snapshot(
        self, task_id: str, before_id: str
    ) -> MentionSnapshotORM | None:
        """Get the most recent snapshot before the given one."""
        before = await self.get_snapshot(before_id)
        if before is None:
            return None
        result = await self.session.execute(
            select(MentionSnapshotORM)
            .where(
                (MentionSnapshotORM.monitor_task_id == task_id)
                & (MentionSnapshotORM.run_at < before.run_at)
            )
            .order_by(MentionSnapshotORM.run_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def list_snapshots_since(
        self, task_id: str, cutoff: datetime
    ) -> list[MentionSnapshotORM]:
        result = await self.session.execute(
            select(MentionSnapshotORM)
            .where(
                (MentionSnapshotORM.monitor_task_id == task_id)
                & (MentionSnapshotORM.run_at >= cutoff)
            )
            .order_by(MentionSnapshotORM.run_at)
        )
        return list(result.scalars().all())
