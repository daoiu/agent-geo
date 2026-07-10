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
    DiagnoseBrandArgs,
    GenerateArticleArgs,
    SearchKnowledgeArgs,
    validate_tool_args,
)

logger = structlog.get_logger()


class ToolExecutor:
    """执行 Agent 工具调用。

    封装 v0.1（DiagnosisService）、v0.2（KnowledgeRepository、ContentWriter）。
    写类工具抛 HumanConfirmationRequired 暂停 ReAct 循环。
    """

    def __init__(self, session_id: str) -> None:
        self.session_id = session_id

    async def execute(self, tool_name: str, args: dict) -> dict:
        """参数校验后分发到对应执行方法。

        Raises:
            ValueError: 未知工具。
            pydantic.ValidationError: 参数不合法。
            HumanConfirmationRequired: 写类工具，需要人工确认。
        """
        # 先校验参数
        validated = validate_tool_args(tool_name, args)

        if tool_name == "diagnose_brand":
            return await self._execute_diagnose_brand(validated)
        if tool_name == "search_knowledge":
            return await self._execute_search_knowledge(validated)
        if tool_name == "generate_article":
            return await self._execute_generate_article(validated)

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

    async def _execute_search_knowledge(self, args: SearchKnowledgeArgs) -> dict:
        """搜索知识库。包装 v0.2 KnowledgeRepository。"""
        # 完整实现在 Task 2.3
        raise NotImplementedError

    async def _execute_generate_article(self, args: GenerateArticleArgs) -> dict:
        """生成文章（待确认）。

        落"待确认"消息到 agent_messages，抛 HumanConfirmationRequired 暂停 ReAct。
        真实生成在 _execute_generate_article_confirmed 中（confirm_action 后触发）。
        """
        # 完整实现在 Task 2.4
        raise NotImplementedError

    async def _execute_generate_article_confirmed(
        self, args: GenerateArticleArgs, checkpoint_message_id: str
    ) -> dict:
        """写类工具确认后真正调 v0.2 ContentWriter。

        仅返回预览，不落库到 v0.2 系统。
        完整实现在 Phase 4 断点续跑（与 run_agent_turn_from_checkpoint 配合）。
        """
        raise NotImplementedError