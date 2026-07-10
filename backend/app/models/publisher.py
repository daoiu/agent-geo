"""Pydantic models for publisher API."""
from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, HttpUrl


class PublisherConfigCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    site_url: HttpUrl
    username: str = Field(..., min_length=1, max_length=100)
    app_password: str = Field(..., min_length=10)


class PublisherConfig(BaseModel):
    """Returned by API. Never includes app_password."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    site_url: str
    username: str
    is_default: bool
    created_at: datetime


class PublishJobStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    CANCELLED = "cancelled"


class PublishJobCreate(BaseModel):
    article_id: str
    config_id: str
    title_override: str | None = Field(None, max_length=300)


class PublishJob(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    article_id: str
    config_id: str
    title_override: str | None
    status: PublishJobStatus
    remote_post_id: int | None
    remote_url: str | None
    error_message: str | None
    published_at: datetime | None
    created_at: datetime
    updated_at: datetime
