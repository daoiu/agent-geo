"""Tests for the GEO scoring engine — IP-critical."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.domain.scorer import WEIGHTS, compute_score_card, generate_suggestions
from app.models.schemas import (
    DimensionScore,
    EeatSignals,
    FreshnessScore,
    MentionResult,
    SchemaCoverage,
    SiteAudit,
    StructureScore,
)


def _make_audit(**overrides) -> SiteAudit:
    defaults = dict(
        url="https://example.com",
        crawl_status="success",
        crawled_at=datetime.now(timezone.utc),
        schema=SchemaCoverage(
            has_organization=True, has_website=True, has_faq=True,
            has_article=True, has_breadcrumb=True, has_product=False,
            detected_schemas=["Organization", "WebSite", "FAQPage", "Article", "BreadcrumbList"],
        ),
        eeat=EeatSignals(
            has_author_bio=True, has_contact_page=True, has_about_page=True,
            third_party_mentions=10, has_expert_attribution=True,
        ),
        structure=StructureScore(
            h1_count_ok=True, heading_hierarchy_valid=True,
            has_lists_or_tables=True, avg_paragraph_length=80,
            bluf_score=0.95,
        ),
        freshness=FreshnessScore(
            last_modified=datetime.now(timezone.utc) - timedelta(days=5),
            days_since_update=5, has_publish_date=True, has_recent_mention_in_content=True,
        ),
        page_load_ms=500,
        robots_txt_allows_ai_bots={"GPTBot": True, "ClaudeBot": True},
    )
    defaults.update(overrides)
    return SiteAudit(**defaults)


def _make_mention(mentioned: bool, position: int | None = 1) -> MentionResult:
    return MentionResult(
        question="q",
        llm_provider="deepseek",
        llm_answer="answer mentioning brand" if mentioned else "no brand here",
        brand_mentioned=mentioned,
        mention_position=position if mentioned else None,
    )


class TestWeights:
    def test_weights_sum_to_one(self) -> None:
        total = sum(WEIGHTS.values())
        assert abs(total - 1.0) < 0.001


class TestScoring:
    def test_perfect_site_with_full_mentions_high_score(self) -> None:
        audit = _make_audit()
        mentions = [_make_mention(mentioned=True) for _ in range(5)]
        card = compute_score_card(audit, mentions)

        assert card.overall >= 85
        assert card.mention_rate == 1.0
        assert card.avg_mention_position == 1.0

    def test_no_mentions_low_relevance(self) -> None:
        audit = _make_audit()
        mentions = [_make_mention(mentioned=False) for _ in range(5)]
        card = compute_score_card(audit, mentions)

        assert card.relevance.score <= 2.0
        assert card.mention_rate == 0.0

    def test_partial_failures_excluded_from_rate(self) -> None:
        audit = _make_audit()
        mentions = [
            _make_mention(mentioned=True),
            _make_mention(mentioned=False),
            MentionResult(question="q", llm_provider="deepseek", llm_answer="",
                          brand_mentioned=False, error="timeout"),
            MentionResult(question="q", llm_provider="deepseek", llm_answer="",
                          brand_mentioned=False, error="timeout"),
        ]
        card = compute_score_card(audit, mentions)

        # 2 valid samples, 1 mentioned → rate = 0.5
        assert card.mention_rate == 0.5

    def test_overall_is_weighted_sum(self) -> None:
        audit = _make_audit()
        mentions = [_make_mention(mentioned=True) for _ in range(3)]
        card = compute_score_card(audit, mentions)

        expected = sum(
            getattr(card, dim).score * getattr(card, dim).weight
            for dim in ["authority", "relevance", "structure", "freshness", "verifiability"]
        ) * 10
        assert abs(card.overall - expected) < 0.01


class TestSuggestions:
    def test_suggests_schema_when_missing(self) -> None:
        audit = _make_audit(schema=SchemaCoverage(has_organization=False, detected_schemas=[]))
        mentions = [_make_mention(mentioned=False)]
        card = compute_score_card(audit, mentions)
        suggestions = generate_suggestions(card, audit, mentions)

        titles = [s.title for s in suggestions]
        assert any("Schema" in t or "结构化" in t for t in titles)

    def test_suggests_bluf_when_score_low(self) -> None:
        audit = _make_audit(structure=StructureScore(h1_count_ok=True, bluf_score=0.2))
        mentions = [_make_mention(mentioned=True)]
        card = compute_score_card(audit, mentions)
        suggestions = generate_suggestions(card, audit, mentions)

        assert any("BLUF" in s.title or "结论先行" in s.title for s in suggestions)

    def test_suggests_ai_bot_blocked(self) -> None:
        audit = _make_audit(robots_txt_allows_ai_bots={"GPTBot": False, "ClaudeBot": True})
        mentions = []
        card = compute_score_card(audit, mentions)
        suggestions = generate_suggestions(card, audit, mentions)

        assert any("robots.txt" in s.title or "爬虫" in s.title for s in suggestions)
