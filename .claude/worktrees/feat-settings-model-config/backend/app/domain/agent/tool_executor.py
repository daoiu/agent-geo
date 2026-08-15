"""v0.4 ToolExecutor：包装 v0.1-v0.3 业务逻辑执行 Agent 工具调用。

工具分类：
- 读类（直接执行）：diagnose_brand、search_knowledge
- 写类（抛 HumanConfirmationRequired 暂停 ReAct 循环）：generate_article

设计原则：
- 不修改 v0.1-v0.3 代码，只包装
- 参数由 validate_tool_args 在 dispatch 前校验
- 写类工具仅持久化"待确认"消息，不直接调 ContentWriter
- 写类工具的真实执行在 ToolExecutor._execute_generate_article_confirmed 中
  （由 confirm_action 端点触发，从断点续跑）
"""
from __future__ import annotations

import structlog

from app.domain.agent.tools import (
    CreateGenerationTaskArgs,
    DiagnoseBrandArgs,
    GenerateArticleArgs,
    ListKnowledgeBasesArgs,
    SearchKnowledgeArgs,
    requires_confirmation,
    validate_tool_args,
)
from app.tasks.task_worker import schedule_task

logger = structlog.get_logger()


class ToolExecutor:
    """执行 Agent 工具调用。

    封装 v0.1（DiagnosisService）、v0.2（KnowledgeRepository、ContentWriter）。
    写类工具抛 HumanConfirmationRequired 暂停 ReAct 循环。
    """

    def __init__(self, session_id: str) -> None:
        self.session_id = session_id
        # v0.6+ Multi-Agent: lazy 加载 specialist(spec §4)
        self._specialist = None

    def _get_specialist(self):
        """lazy 加载 ContentWriterSpecialist(避免循环导入,主 Agent 注入时已就绪)。"""
        if self._specialist is None:
            from app.core.config import get_settings
            from app.core.db import get_session_factory
            from app.domain.agent.content_writer_specialist import ContentWriterSpecialist
            self._specialist = ContentWriterSpecialist(
                settings=get_settings(),
                session_factory=get_session_factory(),
            )
        return self._specialist

    async def execute(self, tool_name: str, args: dict) -> dict:
        """参数校验后分发到对应执行方法。

        v0.6+ P1#13（Task 14）：先查 ``requires_confirmation`` 声明，
        若为 True 则按未来 HITL 路径抛 HumanConfirmationRequired。
        v0.6 P1.6+ 所有工具声明 ``requires_confirmation=False``，直执不暂停。
        """
        # 先校验参数
        validated = validate_tool_args(tool_name, args)

        # v0.6+ P1#13：声明式权限查询（即使 v0.6 P1.6+ 全部 False，路径仍生效便于未来扩展）
        if requires_confirmation(tool_name):
            # 未来扩展点：当某工具声明 requires_confirmation=True 时，
            # 应在此处构造 HumanConfirmationRequired 并 raise。
            # 当前 v0.6 P1.6+ 全部工具声明 False,此分支不进入。
            raise NotImplementedError(
                f"{tool_name} 声明 requires_confirmation=True 但 v0.6 P1.6+ 暂未实现 HITL 路径"
            )

        if tool_name == "diagnose_brand":
            return await self._execute_diagnose_brand(validated)
        if tool_name == "search_knowledge":
            return await self._execute_search_knowledge(validated)
        if tool_name == "list_knowledge_bases":
            return await self._execute_list_knowledge_bases(validated)
        if tool_name == "generate_article":
            return await self._execute_generate_article(validated)
        if tool_name == "create_generation_task":
            return await self._execute_create_generation_task(validated)

        raise ValueError(f"Unknown tool: {tool_name}")

    async def _execute_diagnose_brand(self, args: DiagnoseBrandArgs) -> dict:
        """诊断品牌。包装 v0.1 DiagnosisService。

        策略（用户决策）：走"run 后 get_report"路径，不改 v0.1。
        1. ReportRepository.create 创建 pending ReportORM，得到 task_id
        2. DiagnosisService.run(task_id, req) — v0.1 自己完成爬虫/LLM/打分/写库
        3. ReportRepository.get_by_task_id(task_id) 拉回 ReportORM
        4. 解析 row.report_json 为 Report，提取简化版字段返回

        返回的简化版避免 LLM 上下文爆炸。
        """
        import json

        from app.core.config import get_settings
        from app.core.db import get_session_factory
        from app.domain.crawler import Crawler
        from app.domain.llm_client import LLMClient
        from app.models.schemas import DiagnosisRequest, Report
        from app.repositories.report_repo import ReportRepository
        from app.services.diagnosis_service import DiagnosisService

        settings = get_settings()
        factory = get_session_factory()

        # 1. 创建 Report 记录（v0.1 期望先存在）
        async with factory() as session:
            repo = ReportRepository(session)
            req = DiagnosisRequest(
                brand_name=args.brand_name,
                industry=args.industry,
                official_url=str(args.official_url),
                target_questions=[
                    f"{args.brand_name} 怎么样",
                    f"{args.brand_name} 值得购买吗",
                    f"{args.brand_name} 的主要特点",
                ],
            )
            row = await repo.create(req)
            task_id = row.id
            await session.commit()

        # 2. 调 v0.1 DiagnosisService.run
        async with factory() as session:
            repo = ReportRepository(session)
            crawler = Crawler(settings)
            llm = LLMClient(settings)
            try:
                svc = DiagnosisService(
                    repo=repo, crawler=crawler, llm=llm, settings=settings
                )
                await svc.run(task_id, req)
            finally:
                await crawler.close()

        # 3. 拉回 Report
        async with factory() as session:
            repo = ReportRepository(session)
            row = await repo.get_by_task_id(task_id)

        if row is None or row.report_json is None:
            raise RuntimeError(f"DiagnosisService did not produce report for {task_id}")

        # 4. 解析并提取简化字段
        report = Report.model_validate(json.loads(row.report_json))
        score = report.score_card
        return {
            "report_id": task_id,
            "overall_score": score.overall,
            "mention_rate": score.mention_rate,
            "dimensions": {
                "authority": score.authority.score,
                "relevance": score.relevance.score,
                "structure": score.structure.score,
                "freshness": score.freshness.score,
                "verifiability": score.verifiability.score,
            },
            "suggestions_count": len(report.suggestions),
            "top_suggestion": report.suggestions[0].title if report.suggestions else None,
        }

    async def _execute_list_knowledge_bases(
        self, args: ListKnowledgeBasesArgs
    ) -> dict:
        """列出所有知识库（v0.6 P1.4）.

        返回 [{kb_id, kb_name, doc_count, created_at}]，供 LLM 在模糊提问 /
        不知道 kb_id 时先探索有哪些品牌资料库。doc_count 由 repo 的单 SQL
        LEFT JOIN GROUP BY 一次性给出（无 N+1）。
        """
        from app.core.db import get_session_factory
        from app.repositories.knowledge_repo import KnowledgeRepository

        async with get_session_factory()() as session:
            repo = KnowledgeRepository(session)
            kbs = await repo.list_kbs()

        knowledge_bases = [
            {
                "kb_id": kb.id,
                "kb_name": kb.name,
                "doc_count": kb.doc_count,
                "created_at": kb.created_at.isoformat() if kb.created_at else None,
            }
            for kb in kbs
        ]
        return {
            "knowledge_bases": knowledge_bases,
            "total_count": len(knowledge_bases),
        }

    @staticmethod
    def _normalize_chunk(
        hit: dict, *, kb_id: str | None, kb_name: str | None, doc_filename: str | None
    ) -> dict:
        """把一条召回命中归一化成统一 chunk shape（content 截断 500 字）.

        两个 search 分支（单库 / 跨库）共用，kb_id / kb_name / doc_filename
        由调用方按分支来源填入。
        """
        meta = hit.get("metadata", {}) or {}
        content = (hit.get("content") or "")[:500]
        return {
            "id": hit["id"],
            "doc_id": meta.get("doc_id"),
            "chunk_index": meta.get("chunk_index"),
            "content": content,
            "content_length": len(content),
            "kb_id": kb_id,
            "kb_name": kb_name,
            "doc_filename": doc_filename,
            "rrf_score": hit.get("_rrf_score"),
            "sources": hit.get("_sources", []),
        }

    async def _execute_search_knowledge(self, args: SearchKnowledgeArgs) -> dict:
        """搜索知识库（v0.6 P1.4 双分支）.

        kb_id 不传 → HybridSearch.search_across_kbs（跨库, P1.3）
        kb_id 传   → KnowledgeRepository.search_chunks_hybrid（单库, v0.5）

        chunk content 截断到 500 字符，避免 LLM 上下文爆炸。返回 shape 统一：
        每个 chunk 都带 kb_name / doc_filename（可能为 None），result 带 scope。
        """
        if args.kb_id is None:
            from app.services.hybrid_search import HybridSearch

            hits = await HybridSearch().search_across_kbs(
                query=args.query, top_k=args.limit,
            )
            chunks = [
                self._normalize_chunk(
                    h,
                    kb_id=(h.get("metadata") or {}).get("kb_id"),
                    kb_name=(h.get("metadata") or {}).get("kb_name"),
                    doc_filename=(h.get("metadata") or {}).get("doc_filename"),
                )
                for h in hits
            ]
            return {
                "kb_id": None,
                "kb_name": None,
                "query": args.query,
                "chunks": chunks,
                "total_found": len(chunks),
                "scope": "all_knowledge_bases",
            }

        # kb_id 传：单库路径（v0.5 hybrid, 行为不变）
        # P0#3 阶段 1: 由本层直接调 HybridSearch（之前是 repo.search_chunks_hybrid
        # 委派，已废弃以解除 repositories→services 反向依赖）。
        from sqlalchemy.exc import SQLAlchemyError

        from app.core.db import get_session_factory
        from app.repositories.knowledge_repo import KnowledgeRepository
        from app.services.hybrid_search import HybridSearch

        hits = await HybridSearch().search(
            kb_id=args.kb_id,
            query=args.query,
            top_k=args.limit,
        )

        async with get_session_factory()() as session:
            repo = KnowledgeRepository(session)
            # 回查 KB name 用于 LLM 上下文；DB 层异常降级为 None，不阻断召回
            try:
                kb = await repo.get_kb(args.kb_id)
                kb_name = kb.name if kb else None
            except SQLAlchemyError:
                kb_name = None

        chunks = [
            self._normalize_chunk(
                h, kb_id=args.kb_id, kb_name=kb_name, doc_filename=None,
            )
            for h in hits
        ]
        return {
            "kb_id": args.kb_id,
            "kb_name": kb_name,
            "query": args.query,
            "chunks": chunks,
            "total_found": len(chunks),
            "scope": f"kb:{args.kb_id}",
        }

    async def _execute_generate_article(self, args: GenerateArticleArgs) -> dict:
        """生成文章（v0.6+ Multi-Agent: 走 specialist handoff,纪律 4 失败降级）。

        v0.6 P1.6: 默认走后台，与多篇统一路径。
        v0.6+ Multi-Agent: 走 ContentWriterSpecialist.handoff,失败降级到 _execute_generate_article_legacy。

        与 create_generation_task 的区别：
        - create_generation_task 必须传 kb_id（基于 KB 召回）
        - generate_article 可不传 kb（虽然 GenerateArticleArgs 当前 kb_id 必填——
          v0.4 设计假设用户已在 agent 会话里 list/search 过）

        与 v0.4 老行为（抛 HumanConfirmationRequired）的差异：
        - 老设计：流式预览 + 用户确认 → 实时落 ArticleORM
        - 新设计：所有生成统一后台异步；实时预览需要 opt-in（暂未实现）
        """
        import uuid as _uuid
        from datetime import datetime, timezone

        from app.core.config import get_settings
        from app.domain.agent.handoff import HandoffRequest

        request = HandoffRequest(
            handoff_id=str(_uuid.uuid4()),
            specialist="content_writer",
            task_id=self.session_id,
            session_id=self.session_id,
            started_at=datetime.now(timezone.utc),
            timeout_seconds=get_settings().handoff_timeout_content_writer,
            payload={
                "mode": "single",
                "kb_id": args.kb_id,
                "brand": args.brand,
                "topic": args.topic,
                "keywords": args.keywords,
                "style": args.style,
                "target_length": args.target_length,
                "chunks": [],  # 主 Agent 提前 search_knowledge 召回,此处不重复调
            },
        )

        specialist = self._get_specialist()
        result = await specialist.handoff(request)

        if result.status == "success":
            return result.result
        # 纪律 4: 失败/超时降级到旧路径
        logger.warning(
            "specialist_handoff_failed_falling_back",
            handoff_id=request.handoff_id,
            status=result.status,
            error=result.error,
        )
        return await self._execute_generate_article_legacy(args)

    async def _execute_generate_article_legacy(self, args: GenerateArticleArgs) -> dict:
        """v0.6 P1.6 旧路径,纪律 4 失败降级时使用。

        创建 v0.2 TaskORM (article_count=1) + schedule_task,
        立即返回 task_id。
        """
        from app.core.db import get_session_factory
        from app.repositories.task_repo import TaskRepository

        async with get_session_factory()() as session:
            task_repo = TaskRepository(session)
            task_name = f"{args.brand} - {args.topic}"[:200]
            task = await task_repo.create_task(
                name=task_name,
                kb_id=args.kb_id,
                brand=args.brand,
                topic=args.topic,
                keywords=args.keywords,
                article_count=1,
                style=args.style,
                target_length=args.target_length,
            )

        schedule_task(task.id)

        return {
            "task_id": task.id,
            "kb_id": args.kb_id,
            "article_count": 1,
            "status": task.status,
            "next_step": f"已创建单篇生成任务(specialist 失败,降级旧路径)。请到 /tasks/{task.id} 详情页审核。",
        }

    async def _execute_generate_article_confirmed(
        self, args: GenerateArticleArgs, checkpoint_message_id: str
    ) -> dict:
        """写类工具确认后真正调 v0.2 ContentWriter。

        仅返回预览（spec §4.3），不落库到 v0.2 articles / tasks 表。

        流程：
        1. search_chunks 拿相关 chunks（不写入，仅作 LLM 上下文）
        2. ContentWriter.write_article 生成标题 + 完整正文
        3. content_preview 截断到 300 字符（spec §4.3 '前 300 字符预览'）
        4. 返回 preview shape：{status, title, content_preview, word_count, next_step}
        """
        from app.core.config import get_settings
        from app.core.db import get_session_factory
        from app.domain.generator.content_writer import ContentWriter
        from app.domain.knowledge.retriever import (
            extract_search_keywords,
            search_chunks,
        )

        settings = get_settings()
        factory = get_session_factory()

        # 1. 检索 chunks（注入 LLM prompt 作为'不得编造'的约束）
        query = f"{args.brand} {args.topic}"
        keywords = extract_search_keywords(query)
        async with factory() as session:
            chunks = await search_chunks(
                session=session,
                kb_id=args.kb_id,
                keywords=keywords,
                top_k=5,
            )

        # 2. 调 ContentWriter 生成
        writer = ContentWriter(settings)
        title, content = await writer.write_article(
            brand=args.brand,
            topic=args.topic,
            keywords=args.keywords,
            style=args.style,
            target_length=args.target_length,
            chunks=chunks,
        )

        # 3. 截断预览到 300 字符
        content_preview = content[:300]
        word_count = len(content)

        # 4. 返回 preview shape
        return {
            "status": "generated",
            "title": title,
            "content_preview": content_preview,
            "word_count": word_count,
            "next_step": "如满意此预览，请到 /tasks/new 触发完整生成任务",
        }

    async def _execute_create_generation_task(
        self, args: CreateGenerationTaskArgs
    ) -> dict:
        """创建内容生成任务(v0.6+ Multi-Agent: 走 specialist handoff_batch,纪律 4 失败降级)。

        v0.2 TaskCreator 包装。
        v0.6+ Multi-Agent: 走 ContentWriterSpecialist.handoff_batch,失败降级到 _execute_create_generation_task_legacy。
        """
        import uuid as _uuid
        from datetime import datetime, timezone

        from app.core.config import get_settings
        from app.domain.agent.handoff import HandoffRequest

        request = HandoffRequest(
            handoff_id=str(_uuid.uuid4()),
            specialist="content_writer",
            task_id=self.session_id,
            session_id=self.session_id,
            started_at=datetime.now(timezone.utc),
            timeout_seconds=get_settings().handoff_timeout_content_writer,
            payload={
                "mode": "batch",
                "kb_id": args.kb_id,
                "brand": args.brand,
                "topic": args.topic,
                "keywords": args.keywords,
                "article_count": args.article_count,
                "style": args.style,
                "target_length": args.target_length,
            },
        )

        specialist = self._get_specialist()
        result = await specialist.handoff_batch(request)

        if result.status == "success":
            return result.result
        # 失败降级
        logger.warning(
            "specialist_batch_handoff_failed_falling_back",
            handoff_id=request.handoff_id,
            status=result.status,
            error=result.error,
        )
        return await self._execute_create_generation_task_legacy(args)

    async def _execute_create_generation_task_legacy(
        self, args: CreateGenerationTaskArgs
    ) -> dict:
        """v0.2 TaskCreator 旧路径,纪律 4 失败降级时使用。"""
        from app.core.db import get_session_factory
        from app.repositories.knowledge_repo import KnowledgeRepository
        from app.repositories.task_repo import TaskRepository

        async with get_session_factory()() as session:
            kb_repo = KnowledgeRepository(session)
            kb = await kb_repo.get_kb(args.kb_id)
            if kb is None:
                raise ValueError(f"knowledge base not found: {args.kb_id}")

            task_repo = TaskRepository(session)
            task_name = f"{args.brand} - {args.topic}"[:200]
            task = await task_repo.create_task(
                name=task_name,
                kb_id=args.kb_id,
                brand=args.brand,
                topic=args.topic,
                keywords=args.keywords,
                article_count=args.article_count,
                style=args.style,
                target_length=args.target_length,
            )

        schedule_task(task.id)

        return {
            "task_id": task.id,
            "kb_id": args.kb_id,
            "article_count": args.article_count,
            "status": task.status,
            "next_step": f"已创建任务(specialist 失败,降级旧路径)。请到 /tasks/{task.id} 详情页审核 {args.article_count} 篇草稿。",
        }