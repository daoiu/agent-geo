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
