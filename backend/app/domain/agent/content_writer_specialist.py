"""ContentWriterSpecialist:写文章 specialist(5 条工程纪律全实现)。

设计定位(spec §4):
- 包装 ContentWriterAgent(已有),不重写
- 上下文隔离:只看 (system_prompt + brand + topic + chunks),无 ReAct 状态
- 工具:无工具调用(纯生成)
- 输出:流式文章正文
- 评测:独立 LLM-as-judge(Sprint 3)

5 条工程纪律:
- 纪律 1 幂等键: _check_idempotency 查 handoff_log
- 纪律 2 超时: _execute_with_timeout 包 asyncio.wait_for
- 纪律 3 状态隔离: 独立 session_factory(注入),不持有主 Agent 状态
- 纪律 4 失败回退: 抛 SpecialistHandoffError → 主 Agent 降级调旧路径
- 纪律 5 成本归因: _log_result 落 handoff_log
"""
from __future__ import annotations

import asyncio
import time
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import async_sessionmaker

from app.core.config import Settings
from app.domain.agent.handoff import HandoffRequest, HandoffResult, SpecialistHandoffError
from app.repositories.handoff_log_repo import HandoffLogRepository


class ContentWriterSpecialist:
    """写文章 specialist。"""

    def __init__(
        self,
        settings: Settings,
        session_factory: async_sessionmaker,
    ) -> None:
        self.settings = settings
        self.session_factory = session_factory

    async def handoff(self, request: HandoffRequest) -> HandoffResult:
        """主 Agent 委派入口(单篇文章)。"""
        # 纪律 1: 查幂等
        existing = await self._check_idempotency(request.handoff_id)
        if existing is not None:
            return existing

        # 纪律 2/3/4: 带超时执行 + 异常分类
        timeout = request.timeout_seconds or self.settings.handoff_timeout_content_writer
        start = time.monotonic()
        try:
            payload_result = await asyncio.wait_for(
                self._execute_with_timeout(request.payload),
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
                error=f"超时 {timeout}s",
                duration_ms=duration_ms,
                token_usage={},
            )
        except SpecialistHandoffError as exc:
            duration_ms = int((time.monotonic() - start) * 1000)
            result = HandoffResult(
                handoff_id=request.handoff_id,
                status="failed",
                result=None,
                error=str(exc),
                duration_ms=duration_ms,
                token_usage={},
            )
        except Exception as exc:
            duration_ms = int((time.monotonic() - start) * 1000)
            result = HandoffResult(
                handoff_id=request.handoff_id,
                status="failed",
                result=None,
                error=f"未捕获异常: {exc!r}",
                duration_ms=duration_ms,
                token_usage={},
            )

        # 纪律 5: 落 handoff_log
        await self._log_result(request, result)
        return result

    async def handoff_batch(self, request: HandoffRequest) -> HandoffResult:
        """主 Agent 委派入口(批量任务)。"""
        existing = await self._check_idempotency(request.handoff_id)
        if existing is not None:
            return existing

        timeout = request.timeout_seconds or self.settings.handoff_timeout_content_writer
        start = time.monotonic()
        try:
            payload_result = await asyncio.wait_for(
                self._execute_batch_with_timeout(request.payload),
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
                error=f"批量任务超时 {timeout}s",
                duration_ms=duration_ms,
                token_usage={},
            )
        except Exception as exc:
            duration_ms = int((time.monotonic() - start) * 1000)
            result = HandoffResult(
                handoff_id=request.handoff_id,
                status="failed",
                result=None,
                error=f"批量任务失败: {exc!r}",
                duration_ms=duration_ms,
                token_usage={},
            )

        await self._log_result(request, result)
        return result

    async def _execute_with_timeout(self, payload: dict) -> dict:
        """实际执行(纪律 3: 用独立 session)。

        注: 当前 Task 5 占位实现。Task 6 (tool_executor 改造) 将真实接入 ContentWriterAgent。
        真实集成时调用 ContentWriterAgent.stream_article + 落 ArticleORM + 返回 article_id。
        """
        raise NotImplementedError(
            "ContentWriterSpecialist._execute_with_timeout 在 Task 6 (tool_executor 改造) 中实现真实调用"
        )

    async def _execute_batch_with_timeout(self, payload: dict) -> dict:
        """批量执行(简化,Task 6 实现真实调用)。"""
        raise NotImplementedError(
            "ContentWriterSpecialist._execute_batch_with_timeout 在 Task 6 中实现真实调用"
        )

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
