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

from sqlalchemy.ext.asyncio import async_sessionmaker

from app.core.config import Settings
from app.domain.agent.handoff import HandoffRequest, HandoffResult, SpecialistHandoffError
from app.domain.exceptions import _LLM_TRANSIENT_EXCEPTIONS
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
        # 编程错误让上层处理(不静默吞掉);只兜底 LLM transient 异常
        except _LLM_TRANSIENT_EXCEPTIONS as exc:  # noqa: BLE001
            duration_ms = int((time.monotonic() - start) * 1000)
            result = HandoffResult(
                handoff_id=request.handoff_id,
                status="failed",
                result=None,
                error=f"LLM transient 异常: {exc!r}",
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
        except _LLM_TRANSIENT_EXCEPTIONS as exc:  # noqa: BLE001
            duration_ms = int((time.monotonic() - start) * 1000)
            result = HandoffResult(
                handoff_id=request.handoff_id,
                status="failed",
                result=None,
                error=f"批量任务 LLM transient 异常: {exc!r}",
                duration_ms=duration_ms,
                token_usage={},
            )

        await self._log_result(request, result)
        return result

    async def _execute_with_timeout(self, payload: dict) -> dict:
        """真实执行(纪律 3: 用独立 session)。

        single mode 全链路: 检索 chunks(主 Agent 未提供时自动补检索) →
        ContentWriterAgent.write_article 生成 → 建 TaskORM(article_count=1) +
        落 ArticleORM → 返回 {task_id, article_id, title, content, word_count}。

        LLM transient 失败(content 为空)→ 文章标"生成失败"并抛
        SpecialistHandoffError,由 handoff 标记 failed,主 Agent 降级旧路径。
        """
        from app.domain.generator.content_writer_agent import ContentWriterAgent
        from app.domain.knowledge.retriever import extract_search_keywords, search_chunks
        from app.repositories.task_repo import TaskRepository

        kb_id = payload.get("kb_id")
        brand = payload.get("brand")
        topic = payload.get("topic") or "未命名主题"
        keywords = payload.get("keywords") or []
        style = payload.get("style") or "neutral"
        target_length = payload.get("target_length") or 1500

        async with self.session_factory() as session:
            task_repo = TaskRepository(session)
            task = await task_repo.create_task(
                name=f"{brand} - {topic}"[:200],
                kb_id=kb_id,
                brand=brand,
                topic=topic,
                keywords=keywords,
                article_count=1,
                style=style,
                target_length=target_length,
            )
            article = await task_repo.create_article(task.id, index=0)

            # 主 Agent 提前 search_knowledge 召回的 chunks 未提供时,specialist 补检索
            provided = payload.get("chunks") or []
            if provided:
                chunks_for_prompt = [
                    {"index": i + 1, "content": c.get("content") or c.get("text", "")}
                    for i, c in enumerate(provided)
                ]
                cited = [c.get("id") for c in provided if c.get("id")]
            else:
                query = f"{topic} {' '.join(keywords)}"
                kw = extract_search_keywords(query)
                chunks = await search_chunks(
                    session=session,
                    kb_id=kb_id,
                    keywords=kw,
                    top_k=self.settings.retrieval_top_k,
                )
                chunks_for_prompt = [
                    {"index": i + 1, "content": c.content} for i, c in enumerate(chunks)
                ]
                cited = [c.id for c in chunks]

            writer = ContentWriterAgent(self.settings)
            title, content = await writer.write_article(
                brand=brand,
                topic=topic,
                keywords=keywords,
                style=style,
                target_length=target_length,
                chunks=chunks_for_prompt,
            )

            if not content:
                # LLM transient 失败:标记文章错误,抛给 handoff 走 failed + 降级
                await task_repo.update_article(
                    article.id,
                    title=f"生成失败 #{article.id[:8]}",
                    error_message="LLM 调用失败",
                )
                raise SpecialistHandoffError(
                    f"文章生成失败(LLM transient), task={task.id}, article={article.id}",
                    handoff_id="",
                )

            await task_repo.update_article(
                article.id,
                title=title,
                content=content,
                content_length=len(content),
                cited_chunks=cited,
                llm_provider=(
                    self.settings.enabled_providers[0]
                    if self.settings.enabled_providers
                    else "deepseek"
                ),
            )
            task.status = "completed"
            task.progress = 100
            await session.commit()

        return {
            "task_id": task.id,
            "article_id": article.id,
            "title": title,
            "content": content,
            "word_count": len(content),
            "token_usage": {},
        }

    async def _execute_batch_with_timeout(self, payload: dict) -> dict:
        """批量执行:建 1 个 TaskORM(article_count=N)+ 逐篇生成落 ArticleORM。

        与 v0.2 task_worker 行为对齐:同一 topic 逐篇生成,失败单篇标
        error_message 不中断批次。返回 {task_ids, article_ids}。
        """
        from app.domain.generator.content_writer_agent import ContentWriterAgent
        from app.repositories.task_repo import TaskRepository

        kb_id = payload.get("kb_id")
        brand = payload.get("brand")
        topic = payload.get("topic") or "未命名主题"
        keywords = payload.get("keywords") or []
        article_count = payload.get("article_count") or 3
        style = payload.get("style") or "neutral"
        target_length = payload.get("target_length") or 1500
        topics = payload.get("topics") or []

        async with self.session_factory() as session:
            task_repo = TaskRepository(session)
            task = await task_repo.create_task(
                name=f"{brand} - {topic}"[:200],
                kb_id=kb_id,
                brand=brand,
                topic=topic,
                keywords=keywords,
                article_count=article_count,
                style=style,
                target_length=target_length,
            )
            for i in range(article_count):
                await task_repo.create_article(task.id, index=i)
            articles = await task_repo.list_articles(task.id)

            writer = ContentWriterAgent(self.settings)
            article_ids: list[str] = []
            failed = 0
            for i, article in enumerate(articles):
                per_topic = topics[i] if i < len(topics) else topic
                title, content = await writer.write_article(
                    brand=brand,
                    topic=per_topic,
                    keywords=keywords,
                    style=style,
                    target_length=target_length,
                    chunks=[],
                )
                if not content:
                    failed += 1
                    await task_repo.update_article(
                        article.id,
                        title=f"生成失败 #{i + 1}",
                        error_message="LLM 调用失败",
                    )
                    continue
                await task_repo.update_article(
                    article.id,
                    title=title,
                    content=content,
                    content_length=len(content),
                    cited_chunks=[],
                    llm_provider=(
                        self.settings.enabled_providers[0]
                        if self.settings.enabled_providers
                        else "deepseek"
                    ),
                )
                article_ids.append(article.id)
                progress = int((i + 1) / article_count * 100)
                await task_repo.update_task_status(
                    task.id, status="running", progress=progress
                )

            task = await task_repo.get_task(task.id)
            if task is not None:
                task.status = "completed"
                task.progress = 100
                await session.commit()

        return {
            "task_ids": [task.id],
            "article_ids": article_ids,
            "failed_count": failed,
            "token_usage": {},
        }

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
