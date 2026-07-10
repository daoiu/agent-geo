"""Tests for ToolExecutor (v0.4)."""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from app.domain.agent.tool_executor import ToolExecutor


@pytest.fixture
def executor() -> ToolExecutor:
    return ToolExecutor(session_id="test-session")


class TestDispatch:
    @pytest.mark.asyncio
    async def test_unknown_tool_raises(self, executor: ToolExecutor) -> None:
        """Unknown tool name raises ValueError."""
        with pytest.raises(ValueError, match="Unknown tool"):
            await executor.execute("unknown_tool", {})

    @pytest.mark.asyncio
    async def test_validates_args_before_dispatch(self, executor: ToolExecutor) -> None:
        """Invalid args raise ValidationError before calling the inner method."""
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            await executor.execute("diagnose_brand", {"brand_name": "X"})  # missing others

    @pytest.mark.asyncio
    async def test_dispatches_to_diagnose(self, executor: ToolExecutor) -> None:
        """diagnose_brand calls _execute_diagnose_brand."""
        with patch.object(
            executor,
            "_execute_diagnose_brand",
            new=AsyncMock(return_value={"x": 1}),
        ) as mock_fn:
            result = await executor.execute(
                "diagnose_brand",
                {
                    "brand_name": "X",
                    "industry": "Y",
                    "official_url": "https://example.com",
                },
            )
            mock_fn.assert_called_once()
            assert result == {"x": 1}

    @pytest.mark.asyncio
    async def test_dispatches_to_search(self, executor: ToolExecutor) -> None:
        """search_knowledge calls _execute_search_knowledge."""
        with patch.object(
            executor,
            "_execute_search_knowledge",
            new=AsyncMock(return_value={"y": 2}),
        ) as mock_fn:
            result = await executor.execute(
                "search_knowledge",
                {"kb_id": "kb1", "query": "X"},
            )
            mock_fn.assert_called_once()
            assert result == {"y": 2}

    @pytest.mark.asyncio
    async def test_dispatches_to_generate(self, executor: ToolExecutor) -> None:
        """generate_article calls _execute_generate_article."""
        with patch.object(
            executor,
            "_execute_generate_article",
            new=AsyncMock(return_value={"z": 3}),
        ) as mock_fn:
            result = await executor.execute(
                "generate_article",
                {
                    "kb_id": "kb1",
                    "brand": "X",
                    "topic": "足够长的主题",
                    "keywords": ["k"],
                },
            )
            mock_fn.assert_called_once()
            assert result == {"z": 3}

    @pytest.mark.asyncio
    async def test_session_id_stored(self) -> None:
        """session_id is stored on the executor."""
        ex = ToolExecutor(session_id="my-session")
        assert ex.session_id == "my-session"


class TestDiagnoseBrand:
    """走"run 后 get_report"路径：不改 v0.1 DiagnosisService.run()。"""

    @staticmethod
    def _build_fake_report(
        overall: float = 45.0,
        mention_rate: float = 0.1,
        suggestions: list | None = None,
    ):
        """Build a Report Pydantic object for use in mocked DB rows."""
        from datetime import datetime, timezone

        from app.models.schemas import (
            BrandInfo,
            DimensionScore,
            Report,
            ScoreCard,
            Suggestion,
        )

        if suggestions is None:
            suggestions = [
                Suggestion(
                    priority="P0",
                    category="schema",
                    title="添加 Organization Schema",
                    detail="",
                    expected_impact="",
                    action_steps=[],
                )
            ]
        return Report(
            id="task-123",
            task_id="task-123",
            brand=BrandInfo(name="小米", industry="手机", official_url="https://www.mi.com"),
            score_card=ScoreCard(
                authority=DimensionScore(name="权威度", score=5.0, weight=0.25, evidence=[]),
                relevance=DimensionScore(name="相关性", score=3.0, weight=0.30, evidence=[]),
                structure=DimensionScore(name="结构", score=4.0, weight=0.20, evidence=[]),
                freshness=DimensionScore(name="新鲜", score=6.0, weight=0.15, evidence=[]),
                verifiability=DimensionScore(name="可验证", score=2.0, weight=0.10, evidence=[]),
                overall=overall,
                mention_rate=mention_rate,
                avg_mention_position=2.0,
            ),
            suggestions=suggestions,
            summary="需要系统性优化。",
            created_at=datetime.now(timezone.utc),
            pdf_available=False,
        )

    @staticmethod
    def _build_fake_row(report):
        """Build a ReportORM row carrying the report JSON."""
        from app.models.orm import ReportORM

        return ReportORM(
            id="task-123",
            task_id="task-123",
            brand_name="小米",
            industry="手机",
            official_url="https://www.mi.com",
            status="completed",
            progress=100,
            request_json="{}",
            report_json=report.model_dump_json(),
        )

    @pytest.mark.asyncio
    async def test_returns_simplified_score_card(
        self, executor: ToolExecutor, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """完整流程：mock DiagnosisService.run + mock ReportRepository，让 _execute_diagnose_brand 走通。"""
        fake_report = self._build_fake_report()
        fake_row = self._build_fake_row(fake_report)

        # 1. Mock ReportRepository.create：返回 fake_row
        async def fake_create(self, req):
            return fake_row

        monkeypatch.setattr(
            "app.repositories.report_repo.ReportRepository.create", fake_create
        )

        # 2. Mock DiagnosisService.run：no-op
        class FakeDiagSvc:
            def __init__(self, repo, crawler, llm, settings):
                pass

            async def run(self, task_id, req):
                return None

        monkeypatch.setattr(
            "app.services.diagnosis_service.DiagnosisService", FakeDiagSvc
        )

        # 3. Mock ReportRepository.get_by_task_id：返回 fake_row（带 report_json）
        async def fake_get(self, task_id):
            return fake_row

        monkeypatch.setattr(
            "app.repositories.report_repo.ReportRepository.get_by_task_id", fake_get
        )

        result = await executor._execute_diagnose_brand(
            type("A", (), {
                "brand_name": "小米",
                "industry": "手机",
                "official_url": "https://www.mi.com",
            })()
        )

        assert result["report_id"] == "task-123"
        assert result["overall_score"] == 45.0
        assert result["mention_rate"] == 0.1
        assert result["dimensions"]["authority"] == 5.0
        assert result["dimensions"]["relevance"] == 3.0
        assert result["dimensions"]["structure"] == 4.0
        assert result["dimensions"]["freshness"] == 6.0
        assert result["dimensions"]["verifiability"] == 2.0
        assert result["suggestions_count"] == 1
        assert result["top_suggestion"] == "添加 Organization Schema"

    @pytest.mark.asyncio
    async def test_no_suggestions_returns_none_top(
        self, executor: ToolExecutor, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """没有建议时，top_suggestion 为 None。"""
        fake_report = self._build_fake_report(suggestions=[])
        fake_row = self._build_fake_row(fake_report)

        async def fake_create(self, req):
            return fake_row

        monkeypatch.setattr(
            "app.repositories.report_repo.ReportRepository.create", fake_create
        )

        class FakeDiagSvc:
            def __init__(self, repo, crawler, llm, settings):
                pass

            async def run(self, task_id, req):
                return None

        monkeypatch.setattr(
            "app.services.diagnosis_service.DiagnosisService", FakeDiagSvc
        )

        async def fake_get(self, task_id):
            return fake_row

        monkeypatch.setattr(
            "app.repositories.report_repo.ReportRepository.get_by_task_id", fake_get
        )

        result = await executor._execute_diagnose_brand(
            type("A", (), {
                "brand_name": "X",
                "industry": "Y",
                "official_url": "https://x.com",
            })()
        )

        assert result["suggestions_count"] == 0
        assert result["top_suggestion"] is None

    @pytest.mark.asyncio
    async def test_missing_report_raises(
        self, executor: ToolExecutor, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """如果 v0.1 没生成 report_json，抛 RuntimeError。"""
        from app.models.orm import ReportORM

        empty_row = ReportORM(
            id="task-x",
            task_id="task-x",
            brand_name="X",
            industry="Y",
            official_url="https://x.com",
            status="failed",
            progress=0,
            request_json="{}",
            report_json=None,
        )

        async def fake_create(self, req):
            return empty_row

        monkeypatch.setattr(
            "app.repositories.report_repo.ReportRepository.create", fake_create
        )

        class FakeDiagSvc:
            def __init__(self, repo, crawler, llm, settings):
                pass

            async def run(self, task_id, req):
                return None

        monkeypatch.setattr(
            "app.services.diagnosis_service.DiagnosisService", FakeDiagSvc
        )

        async def fake_get(self, task_id):
            return empty_row

        monkeypatch.setattr(
            "app.repositories.report_repo.ReportRepository.get_by_task_id", fake_get
        )

        with pytest.raises(RuntimeError, match="did not produce report"):
            await executor._execute_diagnose_brand(
                type("A", (), {
                    "brand_name": "X",
                    "industry": "Y",
                    "official_url": "https://x.com",
                })()
            )


class TestSearchKnowledge:
    @pytest.mark.asyncio
    async def test_truncates_long_content_to_500_chars(
        self, executor: ToolExecutor, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """chunk content > 500 字符被截断到 500。"""
        from app.models.orm_v02 import KnowledgeChunkORM

        long_content = "x" * 1000  # > 500

        async def fake_search(*args, **kwargs):
            return [
                KnowledgeChunkORM(
                    id="c1", doc_id="d1", kb_id="kb1", chunk_index=0,
                    content=long_content, content_length=1000,
                )
            ]

        monkeypatch.setattr(
            "app.domain.knowledge.retriever.search_chunks", fake_search
        )

        result = await executor._execute_search_knowledge(
            type("Args", (), {"kb_id": "kb1", "query": "test", "limit": 5})()
        )

        assert result["kb_id"] == "kb1"
        assert result["query"] == "test"
        assert result["total_found"] == 1
        assert len(result["chunks"]) == 1
        assert len(result["chunks"][0]["content"]) == 500  # 截断
        assert result["chunks"][0]["content_length"] == 500  # 反映截断后长度

    @pytest.mark.asyncio
    async def test_keeps_short_content(
        self, executor: ToolExecutor, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """chunk content ≤ 500 字符完整保留。"""
        from app.models.orm_v02 import KnowledgeChunkORM

        short_content = "短内容只有 30 个字符"

        async def fake_search(*args, **kwargs):
            return [
                KnowledgeChunkORM(
                    id="c1", doc_id="d1", kb_id="kb1", chunk_index=0,
                    content=short_content, content_length=len(short_content),
                )
            ]

        monkeypatch.setattr(
            "app.domain.knowledge.retriever.search_chunks", fake_search
        )

        result = await executor._execute_search_knowledge(
            type("Args", (), {"kb_id": "kb1", "query": "test", "limit": 5})()
        )

        assert len(result["chunks"]) == 1
        assert result["chunks"][0]["content"] == short_content
        assert result["chunks"][0]["content_length"] == len(short_content)

    @pytest.mark.asyncio
    async def test_returns_empty_when_no_chunks(
        self, executor: ToolExecutor, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """没有匹配 chunk 时返回空列表。"""
        async def fake_search(*args, **kwargs):
            return []

        monkeypatch.setattr(
            "app.domain.knowledge.retriever.search_chunks", fake_search
        )

        result = await executor._execute_search_knowledge(
            type("Args", (), {"kb_id": "kb1", "query": "无匹配", "limit": 5})()
        )

        assert result["chunks"] == []
        assert result["total_found"] == 0

    @pytest.mark.asyncio
    async def test_chunk_carries_id_and_index(
        self, executor: ToolExecutor, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """返回的 chunk 包含 id / doc_id / chunk_index 字段。"""
        from app.models.orm_v02 import KnowledgeChunkORM

        async def fake_search(*args, **kwargs):
            return [
                KnowledgeChunkORM(
                    id="chunk-abc", doc_id="doc-xyz", kb_id="kb1",
                    chunk_index=3, content="some content", content_length=12,
                )
            ]

        monkeypatch.setattr(
            "app.domain.knowledge.retriever.search_chunks", fake_search
        )

        result = await executor._execute_search_knowledge(
            type("Args", (), {"kb_id": "kb1", "query": "test", "limit": 5})()
        )

        c = result["chunks"][0]
        assert c["id"] == "chunk-abc"
        assert c["doc_id"] == "doc-xyz"
        assert c["chunk_index"] == 3


class TestGenerateArticleConfirmed:
    """_execute_generate_article_confirmed: 真正调 ContentWriter 生成预览（不落库 v0.2）。"""

    @pytest.mark.asyncio
    async def test_returns_preview_shape(
        self, executor: ToolExecutor, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """返回 spec §4.3 的预览 shape：status / title / content_preview / word_count / next_step。"""
        from app.domain.agent.tools import GenerateArticleArgs

        # mock search_chunks 返回 1 个 chunk
        async def fake_search(*args, **kwargs):
            return [
                {
                    "id": "c1",
                    "doc_id": "d1",
                    "kb_id": "kb1",
                    "chunk_index": 0,
                    "content": "已有内容...",
                    "content_length": 5,
                }
            ]

        monkeypatch.setattr(
            "app.domain.knowledge.retriever.search_chunks", fake_search
        )

        # mock ContentWriter.write_article 返回标题 + 完整正文
        class FakeContentWriter:
            def __init__(self, settings):
                pass

            async def write_article(self, **kwargs):
                return ("小米产品评测", "# 小米产品评测\n\n这是完整的 1500 字正文。")

        monkeypatch.setattr(
            "app.domain.generator.content_writer.ContentWriter", FakeContentWriter
        )

        args = GenerateArticleArgs(
            kb_id="kb1", brand="小米", topic="产品评测与体验",
            keywords=["性能", "拍照"], target_length=1500,
        )

        result = await executor._execute_generate_article_confirmed(
            args, checkpoint_message_id="msg-pending-123"
        )

        assert result["status"] == "generated"
        assert result["title"] == "小米产品评测"
        assert result["content_preview"]  # 非空
        assert len(result["content_preview"]) <= 300  # 截断到 300
        assert result["word_count"] > 0
        assert "/tasks/new" in result["next_step"]

    @pytest.mark.asyncio
    async def test_does_not_write_to_v02_db(
        self, executor: ToolExecutor, monkeypatch: pytest.MonkeyPatch, db_session
    ) -> None:
        """关键约束：confirmed 路径不写 v0.2 articles / tasks 表。"""
        from app.domain.agent.tools import GenerateArticleArgs

        async def fake_search(*args, **kwargs):
            return []

        monkeypatch.setattr(
            "app.domain.knowledge.retriever.search_chunks", fake_search
        )

        class FakeContentWriter:
            def __init__(self, settings):
                pass

            async def write_article(self, **kwargs):
                return ("标题", "内容")

        monkeypatch.setattr(
            "app.domain.generator.content_writer.ContentWriter", FakeContentWriter
        )

        args = GenerateArticleArgs(
            kb_id="kb1", brand="小米", topic="产品评测与体验",
            keywords=["性能"], target_length=1500,
        )

        await executor._execute_generate_article_confirmed(args, "msg-id")

        # v0.2 tasks / articles 不应该有任何新行（mock 没动 DB）
        from sqlalchemy import select

        from app.models.orm_v02 import ArticleORM, TaskORM

        task_rows = (await db_session.execute(select(TaskORM))).scalars().all()
        article_rows = (await db_session.execute(select(ArticleORM))).scalars().all()
        assert len(task_rows) == 0
        assert len(article_rows) == 0

    @pytest.mark.asyncio
    async def test_content_preview_truncated_to_300_chars(
        self, executor: ToolExecutor, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """content_preview 截断到 300 字符（spec §4.3 '前 300 字符预览'）。"""
        from app.domain.agent.tools import GenerateArticleArgs

        async def fake_search(*args, **kwargs):
            return []

        monkeypatch.setattr(
            "app.domain.knowledge.retriever.search_chunks", fake_search
        )

        long_content = "x" * 1000  # 1000 字符

        class FakeContentWriter:
            def __init__(self, settings):
                pass

            async def write_article(self, **kwargs):
                return ("长文标题", long_content)

        monkeypatch.setattr(
            "app.domain.generator.content_writer.ContentWriter", FakeContentWriter
        )

        args = GenerateArticleArgs(
            kb_id="kb1", brand="小米", topic="产品评测与体验",
            keywords=["性能"], target_length=1500,
        )

        result = await executor._execute_generate_article_confirmed(args, "msg-id")
        assert len(result["content_preview"]) == 300

    @pytest.mark.asyncio
    async def test_handles_empty_kb(
        self, executor: ToolExecutor, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """KB 为空时（0 chunks）也能生成（ContentWriter 会用空 chunks 调）。"""
        from app.domain.agent.tools import GenerateArticleArgs

        async def fake_search(*args, **kwargs):
            return []

        monkeypatch.setattr(
            "app.domain.knowledge.retriever.search_chunks", fake_search
        )

        class FakeContentWriter:
            def __init__(self, settings):
                pass

            async def write_article(self, **kwargs):
                # chunks 为空列表也能调用（v0.2 ContentWriter 支持）
                return ("标题", "无 KB 内容的文章")

        monkeypatch.setattr(
            "app.domain.generator.content_writer.ContentWriter", FakeContentWriter
        )

        args = GenerateArticleArgs(
            kb_id="kb1", brand="小米", topic="产品评测与体验",
            keywords=["性能"], target_length=1500,
        )

        result = await executor._execute_generate_article_confirmed(args, "msg-id")
        assert result["status"] == "generated"
        assert result["title"] == "标题"


class TestGenerateArticle:
    """generate_article 是写类工具，落'待确认'消息后抛 HumanConfirmationRequired。"""

    @pytest.mark.asyncio
    async def test_raises_human_confirmation_required(
        self, executor: ToolExecutor, db_session
    ) -> None:
        """调用时抛 HumanConfirmationRequired。"""
        from app.domain.agent.tools import GenerateArticleArgs
        from app.domain.exceptions import HumanConfirmationRequired
        from app.models.orm_v04 import AgentSessionORM

        # 先建 session 让外键生效
        sess = AgentSessionORM(id="sess-x", title="T")
        db_session.add(sess)
        await db_session.commit()

        ex = ToolExecutor(session_id="sess-x")
        args = GenerateArticleArgs(
            kb_id="kb1", brand="小米", topic="产品评测与体验",
            keywords=["性能", "拍照"],
        )

        with pytest.raises(HumanConfirmationRequired) as exc_info:
            await ex._execute_generate_article(args)

        assert exc_info.value.tool_name == "generate_article"
        assert exc_info.value.arguments["brand"] == "小米"
        assert exc_info.value.arguments["topic"] == "产品评测与体验"
        assert exc_info.value.arguments["kb_id"] == "kb1"
        assert exc_info.value.arguments["keywords"] == ["性能", "拍照"]
        assert exc_info.value.message_id != ""

    @pytest.mark.asyncio
    async def test_persists_pending_confirmation_message(
        self, executor: ToolExecutor, db_session
    ) -> None:
        """抛异常时已把'待确认'消息落库，pending_confirmation=1。"""
        from sqlalchemy import select

        from app.domain.agent.tools import GenerateArticleArgs
        from app.domain.exceptions import HumanConfirmationRequired
        from app.models.orm_v04 import AgentMessageORM, AgentSessionORM

        # 先建 session
        sess = AgentSessionORM(id="sess-1", title="T")
        db_session.add(sess)
        await db_session.commit()

        ex = ToolExecutor(session_id="sess-1")
        args = GenerateArticleArgs(
            kb_id="kb1", brand="小米", topic="产品评测与体验",
            keywords=["性能", "拍照"],
        )

        try:
            await ex._execute_generate_article(args)
        except HumanConfirmationRequired as e:
            msg_id = e.message_id

            result = await db_session.execute(
                select(AgentMessageORM).where(AgentMessageORM.id == msg_id)
            )
            msg = result.scalar_one_or_none()
            # 全局 factory 已被 db_session fixture 替换，能查到这个 msg
            assert msg is not None
            assert msg.role == "assistant"
            assert msg.pending_confirmation == 1
            assert msg.session_id == "sess-1"
            assert "小米" in msg.content
            assert "产品评测与体验" in msg.content

    @pytest.mark.asyncio
    async def test_pending_message_includes_style_and_length(
        self, executor: ToolExecutor, db_session
    ) -> None:
        """异常 payload 携带完整的 args（style、target_length）。"""
        from app.domain.agent.tools import GenerateArticleArgs
        from app.domain.exceptions import HumanConfirmationRequired
        from app.models.orm_v04 import AgentSessionORM

        sess = AgentSessionORM(id="sess-2", title="T")
        db_session.add(sess)
        await db_session.commit()

        ex = ToolExecutor(session_id="sess-2")
        args = GenerateArticleArgs(
            kb_id="kb1", brand="小米", topic="产品评测与体验",
            keywords=["性能"], style="professional", target_length=2000,
        )

        with pytest.raises(HumanConfirmationRequired) as exc_info:
            await ex._execute_generate_article(args)

        assert exc_info.value.arguments["style"] == "professional"
        assert exc_info.value.arguments["target_length"] == 2000