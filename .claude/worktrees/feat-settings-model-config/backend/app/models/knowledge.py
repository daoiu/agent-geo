"""Pydantic models for knowledge base API."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class KnowledgeBaseCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    description: str | None = Field(None, max_length=1000)


class KnowledgeBase(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    description: str | None
    created_at: datetime
    doc_count: int = 0  # v0.6 P1.4 — 由 LEFT JOIN docs GROUP BY 一次性给出


class KnowledgeDocument(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    kb_id: str
    filename: str
    file_type: str
    file_size: int | None
    parse_status: str
    parse_error: str | None
    chunk_count: int
    created_at: datetime


class KnowledgeChunk(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    doc_id: str
    chunk_index: int
    content: str
    content_length: int


class KnowledgeSearchRequest(BaseModel):
    q: str = Field(..., min_length=1, max_length=200)
    limit: int = Field(5, ge=1, le=50)


class KnowledgeSearchResult(BaseModel):
    query: str
    chunks: list[KnowledgeChunk]


class GlobalKnowledgeHit(BaseModel):
    """A single cross-KB hybrid search hit (v0.6 P1.3).

    Surfaces the source KB + document name so the caller can render
    attribution next to each retrieved chunk.
    """

    kb_id: str
    kb_name: str
    doc_id: str
    doc_filename: str
    chunk_id: str
    chunk_index: int
    content: str
    score: float  # RRF fused score
    sources: list[str]  # subset of {"vector", "keyword"}


class GlobalKnowledgeSearchResult(BaseModel):
    """Response shape for GET /knowledge/search (no kb_id required)."""

    query: str
    hits: list[GlobalKnowledgeHit]
