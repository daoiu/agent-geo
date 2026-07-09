"""Tests for the report renderer."""
from __future__ import annotations

import os
import sys
import tempfile
from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest

from app.domain.renderer import render_html, render_pdf
from app.models.schemas import (
    BrandInfo,
    DimensionScore,
    MentionResult,
    Report,
    ScoreCard,
    SiteAudit,
    Suggestion,
)


@pytest.fixture
def sample_report() -> Report:
    return Report(
        id="r1", task_id="t1",
        brand=BrandInfo(name="小米", industry="手机", official_url="https://www.mi.com"),
        site_audit=SiteAudit(
            url="https://www.mi.com", crawl_status="success",
            crawled_at=datetime.now(timezone.utc),
        ),
        mentions=[
            MentionResult(
                question="手机推荐", llm_provider="deepseek",
                llm_answer="小米不错", brand_mentioned=True,
                mention_position=1, sentiment="positive",
            ),
        ],
        score_card=ScoreCard(
            authority=DimensionScore(name="权威度", score=8.0, weight=0.25, evidence=[]),
            relevance=DimensionScore(name="相关性", score=7.0, weight=0.30, evidence=[]),
            structure=DimensionScore(name="结构", score=6.0, weight=0.20, evidence=[]),
            freshness=DimensionScore(name="新鲜", score=9.0, weight=0.15, evidence=[]),
            verifiability=DimensionScore(name="可验证", score=5.0, weight=0.10, evidence=[]),
            overall=72.5, mention_rate=1.0, avg_mention_position=1.0,
        ),
        suggestions=[
            Suggestion(
                priority="P0", category="schema", title="测试建议",
                detail="详情", action_steps=["步骤1"], expected_impact="效果",
            ),
        ],
        summary="这是摘要",
        created_at=datetime.now(timezone.utc),
    )


class TestRenderHtml:
    def test_returns_string(self, sample_report: Report) -> None:
        html = render_html(sample_report)
        assert isinstance(html, str)
        assert "小米" in html
        assert "GEO 诊断报告" in html
        assert "测试建议" in html


class TestRenderPdf:
    @pytest.fixture
    def mock_weasyprint(self) -> MagicMock:
        """Mock weasyprint module since GTK3 runtime is unavailable on Windows."""
        mock_wp = MagicMock()
        mock_html_instance = MagicMock()
        mock_wp.HTML.return_value = mock_html_instance
        mock_wp.CSS.return_value = MagicMock()

        # Simulate write_pdf writing a minimal valid PDF to the path
        def fake_write_pdf(path: str, **kwargs) -> None:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "wb") as f:
                f.write(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")

        mock_html_instance.write_pdf.side_effect = fake_write_pdf

        return mock_wp

    def test_writes_pdf_file(
        self, sample_report: Report, mock_weasyprint: MagicMock
    ) -> None:
        """Test PDF rendering with WeasyPrint mocked.

        Note: WeasyPrint requires GTK3 runtime which is not available on
        Windows without system dependencies. This test mocks WeasyPrint
        to verify the render_pdf contract (correct call arguments and
        return value), while render_html is tested for real.
        """
        # Patch sys.modules to replace weasyprint with our mock
        original_weasyprint = sys.modules.get("weasyprint")
        sys.modules["weasyprint"] = mock_weasyprint

        try:
            with tempfile.TemporaryDirectory() as tmp:
                out = os.path.join(tmp, "report.pdf")
                result_path = render_pdf(sample_report, out)

                # Verify correct output path is returned
                assert result_path == out

                # Verify PDF file was created
                assert os.path.exists(result_path)
                assert os.path.getsize(result_path) > 0

                # Verify it's a PDF
                with open(result_path, "rb") as f:
                    header = f.read(5)
                assert header == b"%PDF-"

                # Verify WeasyPrint was called correctly
                mock_weasyprint.HTML.assert_called_once()
                call_kwargs = mock_weasyprint.HTML.call_args.kwargs
                assert "string" in call_kwargs
                assert "小米" in call_kwargs["string"]
                assert "GEO 诊断报告" in call_kwargs["string"]

                mock_html_instance = mock_weasyprint.HTML.return_value
                mock_html_instance.write_pdf.assert_called_once()
        finally:
            # Restore original weasyprint in sys.modules
            if original_weasyprint is not None:
                sys.modules["weasyprint"] = original_weasyprint
            elif "weasyprint" in sys.modules:
                del sys.modules["weasyprint"]

    def test_weasyprint_unavailable_still_imports_render_html(
        self, sample_report: Report
    ) -> None:
        """Verify render_html works even if WeasyPrint is unavailable."""
        # render_html should work without WeasyPrint since import is deferred
        html = render_html(sample_report)
        assert "小米" in html
        assert isinstance(html, str)
