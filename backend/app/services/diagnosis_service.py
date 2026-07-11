"""Orchestrates the full diagnosis pipeline for one task."""
from __future__ import annotations

from datetime import datetime, timezone

import structlog

from app.core.config import Settings
from app.domain.crawler import Crawler
from app.domain.exceptions import CrawlError, DomainError, LlmError, RenderError, ScoreError
from app.domain.llm_client import LLMClient
from app.domain.renderer import render_pdf
from app.domain.scorer import compute_score_card, generate_suggestions
from app.models.schemas import (
    BrandInfo,
    DiagnosisRequest,
    Report,
    SiteAudit,
)
from app.repositories.report_repo import ReportRepository

logger = structlog.get_logger()


class DiagnosisService:
    """Runs the full diagnosis pipeline for one task."""

    def __init__(
        self,
        repo: ReportRepository,
        crawler: Crawler,
        llm: LLMClient,
        settings: Settings,
    ) -> None:
        self.repo = repo
        self.crawler = crawler
        self.llm = llm
        self.settings = settings

    async def run(self, task_id: str, req: DiagnosisRequest) -> None:
        """Execute pipeline: crawl → LLM → score → save report.

        Updates DB at each stage. On failure, marks task as failed.
        """
        try:
            # Stage 1: Crawl
            await self.repo.update_status(task_id, status="crawling", progress=10)
            site_audit: SiteAudit | None = None
            try:
                site_audit = await self.crawler.audit(str(req.official_url))
            except CrawlError as e:
                logger.error("crawl_failed", task_id=task_id, error=str(e))
                await self.repo.update_status(
                    task_id, status="failed", progress=0, error=f"官网无法访问：{e.reason}"
                )
                return

            # Stage 2: LLM
            await self.repo.update_status(task_id, status="querying_llm", progress=30)
            mentions = await self.llm.query_mentions(
                brand=req.brand_name,
                industry=req.industry,
                questions=req.target_questions,
            )
            logger.info("llm_done", task_id=task_id, n_mentions=len(mentions))

            # Stage 3: Scoring
            await self.repo.update_status(task_id, status="scoring", progress=70)
            card = compute_score_card(site_audit, mentions)
            suggestions = generate_suggestions(card, site_audit, mentions)
            summary = await self._generate_summary(req, card)

            # Stage 4: Build report
            await self.repo.update_status(task_id, status="rendering", progress=90)
            report = Report(
                id=task_id,
                task_id=task_id,
                brand=BrandInfo(
                    name=req.brand_name,
                    industry=req.industry,
                    official_url=str(req.official_url),
                ),
                site_audit=site_audit,
                mentions=mentions,
                score_card=card,
                suggestions=suggestions,
                summary=summary,
                created_at=datetime.now(timezone.utc),
                pdf_available=False,
            )

            # Save HTML report to DB (PDF is generated on-demand in API)
            report_json = report.model_dump_json()
            await self.repo.update_report(task_id, report_json=report_json)

            await self.repo.update_status(task_id, status="completed", progress=100)
            logger.info("diagnosis_completed", task_id=task_id, overall=card.overall)

        except DomainError as e:
            logger.exception("domain_error", task_id=task_id)
            await self.repo.update_status(
                task_id, status="failed", progress=0, error=f"{type(e).__name__}: {e}"
            )
        except Exception as e:  # noqa: BLE001
            logger.exception("unexpected_error", task_id=task_id)
            await self.repo.update_status(
                task_id, status="failed", progress=0, error=f"unexpected: {type(e).__name__}"
            )

    async def _generate_summary(self, req: DiagnosisRequest, card) -> str:
        """Generate executive summary via LLM. Falls back to template on failure."""
        try:
            prompt = (
                f"品牌「{req.brand_name}」({req.industry}) 的 GEO 诊断总分为 "
                f"{card.overall:.1f}/100。请用 2-3 句话给出执行摘要，"
                f"指出最重要的 1-2 个改进方向。语言：简体中文。"
            )
            # Use DeepSeek directly for summary
            from openai import AsyncOpenAI

            from app.domain.llm_client import _normalize_base_url

            client = AsyncOpenAI(
                api_key=self.settings.deepseek_api_key,
                base_url=_normalize_base_url(self.settings.deepseek_base_url),
                timeout=15,
            )
            response = await client.chat.completions.create(
                model=self.settings.deepseek_model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.5,
            )
            return response.choices[0].message.content or _fallback_summary(card)
        except Exception:  # noqa: BLE001
            return _fallback_summary(card)


def _fallback_summary(card) -> str:
    score = card.overall
    if score >= 80:
        return f"品牌 GEO 健康度优秀（{score:.1f}/100），建议持续维护并监控趋势。"
    if score >= 60:
        return f"品牌 GEO 健康度良好（{score:.1f}/100），有明确的改进空间。"
    if score >= 40:
        return f"品牌 GEO 健康度中等（{score:.1f}/100），需要系统性优化。"
    return f"品牌 GEO 健康度较弱（{score:.1f}/100），建议优先处理 P0 级建议。"
