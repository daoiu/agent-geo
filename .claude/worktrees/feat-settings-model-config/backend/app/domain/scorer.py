"""Five-dimension GEO scoring engine.

Dimensions (weights in `WEIGHTS`):
  - authority (0.25): E-E-A-T signals
  - relevance (0.30): AI mention rate
  - structure (0.20): heading hierarchy, BLUF, paragraph length
  - freshness (0.15): content update frequency
  - verifiability (0.10): schema + structured data coverage

Each dimension is scored 0-10. Overall = weighted sum * 10 (range 0-100).
"""
from __future__ import annotations

from app.models.schemas import (
    DimensionScore,
    EeatSignals,
    FreshnessScore,
    MentionResult,
    SchemaCoverage,
    ScoreCard,
    SiteAudit,
    StructureScore,
    Suggestion,
)

WEIGHTS: dict[str, float] = {
    "authority": 0.25,
    "relevance": 0.30,
    "structure": 0.20,
    "freshness": 0.15,
    "verifiability": 0.10,
}


def _score_authority(audit: SiteAudit) -> DimensionScore:
    """Score based on EEAT signals (0-10)."""
    eeat: EeatSignals = audit.eeat
    score = 0.0
    evidence: list[str] = []

    if eeat.has_about_page:
        score += 2
        evidence.append("有 About 页面")
    if eeat.has_contact_page:
        score += 2
        evidence.append("有 Contact 页面")
    if eeat.has_author_bio:
        score += 2
        evidence.append("有作者署名")
    if eeat.has_expert_attribution:
        score += 1
        evidence.append("有专家背书")
    # 3rd party mentions: scale 0-10 mentions → 0-3 points
    third_party_pts = min(eeat.third_party_mentions / 10 * 3, 3)
    score += third_party_pts
    if third_party_pts > 0:
        evidence.append(f"第三方权威源提及 {eeat.third_party_mentions} 次")

    return DimensionScore(
        name="权威度",
        score=min(score, 10),
        weight=WEIGHTS["authority"],
        evidence=evidence,
    )


def _score_relevance(mentions: list[MentionResult]) -> DimensionScore:
    """Score based on AI mention rate (0-10)."""
    valid = [m for m in mentions if m.error is None]
    evidence: list[str] = []

    if not valid:
        return DimensionScore(
            name="内容相关性", score=0, weight=WEIGHTS["relevance"],
            evidence=["无有效 LLM 样本"],
        )

    mentioned = [m for m in valid if m.brand_mentioned]
    rate = len(mentioned) / len(valid)
    # Linear: 100% mention → 10, 0% → 0
    base_score = rate * 10

    evidence.append(f"AI 提及率 {rate*100:.0f}% ({len(mentioned)}/{len(valid)})")
    if mentioned:
        avg_pos = sum(m.mention_position or 99 for m in mentioned) / len(mentioned)
        evidence.append(f"平均提及位置 {avg_pos:.1f}")
        # Bonus for early mention
        if avg_pos <= 2:
            base_score = min(base_score + 0.5, 10)

    return DimensionScore(
        name="内容相关性", score=base_score, weight=WEIGHTS["relevance"], evidence=evidence,
    )


def _score_structure(audit: SiteAudit) -> DimensionScore:
    """Score based on heading hierarchy + BLUF (0-10)."""
    s: StructureScore = audit.structure
    score = 0.0
    evidence: list[str] = []

    if s.h1_count_ok:
        score += 3
        evidence.append("H1 数量正确 (1个)")
    if s.heading_hierarchy_valid:
        score += 2
        evidence.append("标题层级合规 (H1→H2→H3)")
    if s.has_lists_or_tables:
        score += 2
        evidence.append("使用了列表或表格")
    # BLUF
    score += s.bluf_score * 3
    if s.bluf_score >= 0.8:
        evidence.append("结论先行 (BLUF) 评分高")

    return DimensionScore(
        name="内容结构", score=min(score, 10), weight=WEIGHTS["structure"], evidence=evidence,
    )


def _score_freshness(audit: SiteAudit) -> DimensionScore:
    """Score based on content update recency (0-10)."""
    f: FreshnessScore = audit.freshness
    score = 0.0
    evidence: list[str] = []

    if f.days_since_update is None:
        evidence.append("无法判断更新时间")
        return DimensionScore(
            name="更新频率", score=2, weight=WEIGHTS["freshness"], evidence=evidence,
        )

    days = f.days_since_update
    if days <= 7:
        score = 10
        evidence.append(f"{days} 天前更新（极新鲜）")
    elif days <= 30:
        score = 8
        evidence.append(f"{days} 天前更新（新鲜）")
    elif days <= 90:
        score = 5
        evidence.append(f"{days} 天前更新（中等）")
    elif days <= 365:
        score = 3
        evidence.append(f"{days} 天前更新（陈旧）")
    else:
        score = 1
        evidence.append(f"{days} 天前更新（非常陈旧）")

    if f.has_recent_mention_in_content:
        score = min(score + 1, 10)
        evidence.append("内容中提及当年/最新年份")

    return DimensionScore(
        name="更新频率", score=score, weight=WEIGHTS["freshness"], evidence=evidence,
    )


def _score_verifiability(audit: SiteAudit) -> DimensionScore:
    """Score based on structured data coverage (0-10)."""
    s: SchemaCoverage = audit.schema
    detected = len(s.detected_schemas)
    score = min(detected * 2, 10)
    evidence = [f"已部署 {detected} 种 Schema: {', '.join(s.detected_schemas) or '无'}"]

    # Penalty if AI bots blocked
    blocked_bots = [b for b, allowed in audit.robots_txt_allows_ai_bots.items() if not allowed]
    if blocked_bots:
        score = max(score - 2, 0)
        evidence.append(f"⚠️ 以下 AI 爬虫被 robots.txt 屏蔽: {', '.join(blocked_bots)}")

    return DimensionScore(
        name="数据可验证性", score=score, weight=WEIGHTS["verifiability"], evidence=evidence,
    )


def compute_score_card(
    site_audit: SiteAudit | None,
    mentions: list[MentionResult],
) -> ScoreCard:
    """Compute the five-dimension score card.

    If site_audit is None (crawl failed), structure/freshness/etc default to 0.
    """
    if site_audit is None:
        # Cannot score site-dependent dimensions
        empty = DimensionScore(name="x", score=0, weight=0, evidence=[])
        return ScoreCard(
            authority=empty, relevance=empty, structure=empty,
            freshness=empty, verifiability=empty,
            overall=0, mention_rate=0.0, avg_mention_position=None,
        )

    authority = _score_authority(site_audit)
    relevance = _score_relevance(mentions)
    structure = _score_structure(site_audit)
    freshness = _score_freshness(site_audit)
    verifiability = _score_verifiability(site_audit)

    overall = (
        authority.score * authority.weight
        + relevance.score * relevance.weight
        + structure.score * structure.weight
        + freshness.score * freshness.weight
        + verifiability.score * verifiability.weight
    ) * 10

    # Mention rate / avg position
    valid = [m for m in mentions if m.error is None]
    mentioned = [m for m in valid if m.brand_mentioned]
    rate = len(mentioned) / len(valid) if valid else 0.0
    avg_pos = (
        sum(m.mention_position for m in mentioned if m.mention_position is not None)
        / len(mentioned)
        if mentioned else None
    )

    return ScoreCard(
        authority=authority, relevance=relevance, structure=structure,
        freshness=freshness, verifiability=verifiability,
        overall=overall, mention_rate=rate, avg_mention_position=avg_pos,
    )


def generate_suggestions(
    card: ScoreCard,
    audit: SiteAudit | None,
    mentions: list[MentionResult],
) -> list[Suggestion]:
    """Produce actionable suggestions based on the scorecard."""
    suggestions: list[Suggestion] = []

    # Schema-related
    if audit and len(audit.schema.detected_schemas) < 3:
        suggestions.append(Suggestion(
            priority="P0",
            category="schema",
            title="部署基础 Schema.org 结构化数据",
            detail=(
                "当前页面缺少 Organization / WebSite / Article 等基础结构化数据。"
                "AI 引擎在解析页面时无法可靠识别品牌实体。"
            ),
            action_steps=[
                "在 <head> 中添加 Organization JSON-LD（包含 name、url、logo）",
                "为关键页面添加 WebSite 和 BreadcrumbList",
                "使用 Google Rich Results Test 验证部署",
            ],
            expected_impact="提升 AI 引擎对品牌实体的识别度，预计整体评分 +5-10 分",
        ))

    # AI bots blocked
    if audit:
        blocked = [b for b, ok in audit.robots_txt_allows_ai_bots.items() if not ok]
        if blocked:
            suggestions.append(Suggestion(
                priority="P0",
                category="robots",
                title="放开 AI 爬虫的 robots.txt 限制",
                detail=(
                    f"当前 robots.txt 屏蔽了 {len(blocked)} 个 AI 爬虫 "
                    f"({', '.join(blocked)})，导致这些引擎无法抓取您的内容。"
                ),
                action_steps=[
                    f"在 robots.txt 中为 {', '.join(blocked)} 添加 Allow: /",
                    "或使用 User-agent: * 配合 Allow: / 全局放开",
                ],
                expected_impact="让被屏蔽的 AI 引擎能够抓取并引用您的内容",
            ))

    # Mention rate low
    valid = [m for m in mentions if m.error is None]
    if valid:
        rate = len([m for m in valid if m.brand_mentioned]) / len(valid)
        if rate < 0.5:
            suggestions.append(Suggestion(
                priority="P0",
                category="content",
                title="提升品牌在 AI 答案中的提及率",
                detail=(
                    f"在测试的 {len(valid)} 个问题中，AI 仅在 {rate*100:.0f}% 的答案中"
                    f"提到了您的品牌。需要让品牌信息在 AI 训练/检索数据中更突出。"
                ),
                action_steps=[
                    "在官网发布结构化的 FAQ，覆盖用户常问的问题",
                    "在权威第三方平台（知乎、微信公众号、行业媒体）发布带品牌的深度内容",
                    "为关键产品页添加 HowTo 和 FAQPage Schema",
                ],
                expected_impact="提升 AI 引用权重，预计提及率提升 20-40%",
            ))

    # BLUF
    if audit and audit.structure.bluf_score < 0.6:
        suggestions.append(Suggestion(
            priority="P1",
            category="structure",
            title="使用 BLUF（结论先行）写作结构",
            detail=(
                "您的内容未在开头给出明确结论。AI 引擎倾向于引用"
                "段落级别独立可读的句子——结论埋得越深，越难被引用。"
            ),
            action_steps=[
                "在每篇文章前 100 字内给出核心结论",
                "每段第一句话必须是该段的核心主张",
                "避免大段铺垫，直接回答'是什么 / 为什么 / 怎么做'",
            ],
            expected_impact="段落级引用概率显著提升",
        ))

    # Freshness
    if audit and audit.freshness.days_since_update is not None and audit.freshness.days_since_update > 90:
        suggestions.append(Suggestion(
            priority="P1",
            category="freshness",
            title="更新陈旧内容",
            detail=(
                f"核心内容已 {audit.freshness.days_since_update} 天未更新。"
                "AI 引擎会降低对陈旧内容的引用权重。"
            ),
            action_steps=[
                "为关键页面设置 30 天更新一次的节奏",
                "添加 datePublished 和 dateModified 元数据",
                "在内容中提及当前年份以表明时效性",
            ],
            expected_impact="新鲜度评分提升 3-5 分",
        ))

    # Authority
    if audit and not audit.eeat.has_author_bio:
        suggestions.append(Suggestion(
            priority="P1",
            category="eeat",
            title="添加作者署名和专业背景",
            detail=(
                "页面缺少明确的作者信息和专业背景。"
                "E-E-A-T 中 Experience 和 Expertise 信号不足。"
            ),
            action_steps=[
                "为每篇文章添加作者署名 + 个人简介",
                "作者简介中体现行业经验和资质",
                "在 About 页面展示团队专业背景",
            ],
            expected_impact="权威度评分提升 2-3 分",
        ))

    return suggestions
