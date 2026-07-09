"""Pydantic models for API + domain layer."""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, HttpUrl


class TaskStatus(str, Enum):
    """Lifecycle states of a diagnosis task."""

    PENDING = "pending"
    CRAWLING = "crawling"
    QUERYING_LLM = "querying_llm"
    SCORING = "scoring"
    RENDERING = "rendering"
    COMPLETED = "completed"
    FAILED = "failed"


# --- Request ---


class DiagnosisRequest(BaseModel):
    """User-submitted diagnosis request."""

    brand_name: str = Field(..., min_length=1, max_length=100)
    industry: str = Field(..., min_length=1, max_length=100)
    official_url: HttpUrl
    target_questions: list[str] = Field(..., min_length=3, max_length=5)
    competitors: list[str] = Field(default_factory=list, max_length=10)
    contact_email: EmailStr | None = None


# --- Task lifecycle ---


class DiagnosisTask(BaseModel):
    """Task state exposed via status polling API."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    request: DiagnosisRequest
    status: TaskStatus
    progress: int = Field(..., ge=0, le=100)
    error_message: str | None = None
    created_at: datetime
    updated_at: datetime


# --- Mention / LLM result ---


class MentionResult(BaseModel):
    """Result of asking one question to one LLM."""

    question: str
    llm_provider: str
    llm_answer: str
    brand_mentioned: bool
    mention_position: int | None = None
    competitors_mentioned: list[str] = Field(default_factory=list)
    sentiment: Literal["positive", "neutral", "negative"] = "neutral"
    error: str | None = None  # set when this sample should be excluded from rates


# --- Site audit sub-models ---


class SchemaCoverage(BaseModel):
    has_organization: bool = False
    has_website: bool = False
    has_faq: bool = False
    has_article: bool = False
    has_breadcrumb: bool = False
    has_product: bool = False
    detected_schemas: list[str] = Field(default_factory=list)


class EeatSignals(BaseModel):
    has_author_bio: bool = False
    has_contact_page: bool = False
    has_about_page: bool = False
    third_party_mentions: int = 0
    has_expert_attribution: bool = False


class StructureScore(BaseModel):
    h1_count_ok: bool = False
    heading_hierarchy_valid: bool = False
    has_lists_or_tables: bool = False
    avg_paragraph_length: int = 0
    bluf_score: float = 0.0


class FreshnessScore(BaseModel):
    last_modified: datetime | None = None
    days_since_update: int | None = None
    has_publish_date: bool = False
    has_recent_mention_in_content: bool = False


class SiteAudit(BaseModel):
    url: str
    crawl_status: Literal["success", "partial", "failed"] = "success"
    crawled_at: datetime
    schema: SchemaCoverage = Field(default_factory=SchemaCoverage)
    eeat: EeatSignals = Field(default_factory=EeatSignals)
    structure: StructureScore = Field(default_factory=StructureScore)
    freshness: FreshnessScore = Field(default_factory=FreshnessScore)
    page_load_ms: int | None = None
    robots_txt_allows_ai_bots: dict[str, bool] = Field(default_factory=dict)


# --- Scoring ---


class DimensionScore(BaseModel):
    name: str
    score: float = Field(..., ge=0, le=10)
    weight: float = Field(..., ge=0, le=1)
    evidence: list[str] = Field(default_factory=list)


class ScoreCard(BaseModel):
    authority: DimensionScore
    relevance: DimensionScore
    structure: DimensionScore
    freshness: DimensionScore
    verifiability: DimensionScore
    overall: float = Field(..., ge=0, le=100)
    mention_rate: float = Field(..., ge=0, le=1)
    avg_mention_position: float | None = None


class Suggestion(BaseModel):
    priority: Literal["P0", "P1", "P2"]
    category: str
    title: str
    detail: str
    action_steps: list[str] = Field(default_factory=list)
    expected_impact: str


# --- Brand info / final report ---


class BrandInfo(BaseModel):
    name: str
    industry: str
    official_url: str


class Report(BaseModel):
    id: str
    task_id: str
    brand: BrandInfo
    site_audit: SiteAudit | None = None
    mentions: list[MentionResult] = Field(default_factory=list)
    score_card: ScoreCard
    suggestions: list[Suggestion] = Field(default_factory=list)
    summary: str
    created_at: datetime
    pdf_available: bool = False
