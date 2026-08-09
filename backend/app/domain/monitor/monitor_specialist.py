"""MonitorSpecialist:监测 specialist(5 条工程纪律全实现)。

设计定位(spec §5):
- 包装 MonitorService.execute_monitor_run(已有),不重写
- 上下文隔离:只看 (brand + industry + questions + providers),无 ReAct 状态
- 工具:无工具调用(纯查询+判定)
- 调度:APScheduler 触发(不变),内部走 specialist 路径
- 评测:独立监测质量评估

handoff_id 派生(spec §5.2):
- f"monitor-{monitor_task_id}-{started_at.isoformat()}"
- 同 monitor_task 不同时刻是独立执行(避免 24h 幂等窗口吃掉正常定时任务)
"""
from __future__ import annotations

import asyncio
import time
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import async_sessionmaker

from app.core.config import Settings
from app.domain.agent.handoff import HandoffRequest, HandoffResult
from app.domain.exceptions import _LLM_TRANSIENT_EXCEPTIONS
from app.domain.monitor.monitor_service import execute_monitor_run
from app.repositories.handoff_log_repo import HandoffLogRepository


class MonitorSpecialist:
    """监测 specialist。"""

    def __init__(
        self,
        settings: Settings,
        session_factory: async_sessionmaker,
    ) -> None:
        self.settings = settings
        self.session_factory = session_factory

    @staticmethod
    def _derive_handoff_id(monitor_task_id: str, started_at: datetime) -> str:
        """handoff_id 派生规则(spec §5.2)。"""
        return f"monitor-{monitor_task_id}-{started_at.isoformat()}"

    async def run(self, monitor_task_id: str) -> HandoffResult:
        """APScheduler 触发入口(spec §5.1)。"""
        started_at = datetime.now(timezone.utc)
        handoff_id = self._derive_handoff_id(monitor_task_id, started_at)

        request = HandoffRequest(
            handoff_id=handoff_id,
            specialist="monitor",
            task_id=monitor_task_id,
            session_id="ap_scheduler",  # monitor 无 session,标记来源
            started_at=started_at,
            timeout_seconds=self.settings.handoff_timeout_monitor,
            payload={"monitor_task_id": monitor_task_id},
        )

        existing = await self._check_idempotency(request.handoff_id)
        if existing is not None:
            return existing

        timeout = self.settings.handoff_timeout_monitor
        start = time.monotonic()
        try:
            payload_result = await asyncio.wait_for(
                self._execute_with_timeout(monitor_task_id),
                timeout=timeout,
            )
            duration_ms = int((time.monotonic() - start) * 1000)
            result = HandoffResult(
                handoff_id=request.handoff_id,
                status="success",
                result=payload_result,
                error=None,
                duration_ms=duration_ms,
                token_usage=payload_result.get("token_usage", {}),
            )
        except asyncio.TimeoutError:
            duration_ms = int((time.monotonic() - start) * 1000)
            result = HandoffResult(
                handoff_id=request.handoff_id,
                status="timeout",
                result=None,
                error=f"monitor 超时 {timeout}s",
                duration_ms=duration_ms,
                token_usage={},
            )
        except _LLM_TRANSIENT_EXCEPTIONS as exc:  # noqa: BLE001
            # 纪律 4: 降级到 monitor_service.execute_monitor_run
            try:
                await execute_monitor_run(monitor_task_id)
                result = HandoffResult(
                    handoff_id=request.handoff_id,
                    status="failed",
                    result=None,
                    error=f"specialist 失败,降级到旧路径: {exc!r}",
                    duration_ms=int((time.monotonic() - start) * 1000),
                    token_usage={},
                )
            except _LLM_TRANSIENT_EXCEPTIONS as legacy_exc:  # noqa: BLE001
                duration_ms = int((time.monotonic() - start) * 1000)
                result = HandoffResult(
                    handoff_id=request.handoff_id,
                    status="failed",
                    result=None,
                    error=f"specialist + legacy 都失败: {exc!r} / {legacy_exc!r}",
                    duration_ms=duration_ms,
                    token_usage={},
                )

        await self._log_result(request, result)
        return result

    async def _execute_with_timeout(self, monitor_task_id: str) -> dict:
        """真实执行:复用 MonitorService 核心逻辑(LLM 查询 + snapshot)。

        纪律 3: 用注入的 session_factory(不碰主 Agent session)。
        返回 {monitor_task_id, snapshot_id, mention_rate, ...} 供 handoff 结果。
        """
        from app.domain.monitor.monitor_service import _run_monitor_core

        async with self.session_factory() as session:
            return await _run_monitor_core(session, self.settings, monitor_task_id)

    async def _check_idempotency(self, handoff_id: str) -> HandoffResult | None:
        """纪律 1: 查 handoff_log。"""
        async with self.session_factory() as session:
            repo = HandoffLogRepository(session)
            return await repo.check_idempotency(
                handoff_id,
                window_hours=self.settings.handoff_idempotency_window_hours,
            )

    async def _log_result(self, request: HandoffRequest, result: HandoffResult) -> None:
        """纪律 5: 落 handoff_log。"""
        async with self.session_factory() as session:
            repo = HandoffLogRepository(session)
            await repo.insert(request, result)
            await session.commit()
