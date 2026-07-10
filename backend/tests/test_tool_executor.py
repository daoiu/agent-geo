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