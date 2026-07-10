"""Pydantic models for monitor API."""
from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class MonitorFrequency(str, Enum):
    HOURLY = "hourly"
    DAILY = "daily"
    WEEKLY = "weekly"


class MonitorTaskCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    brand: str = Field(..., min_length=1, max_length=100)
    industry: str = Field(..., min_length=1, max_length=100)
    target_questions: list[str] = Field(..., min_length=1, max_length=5)
    frequency: MonitorFrequency = MonitorFrequency.DAILY
    providers: list[str] = Field(default_factory=lambda: ["deepseek"])
    notify_email: EmailStr | None = None
    change_threshold: float = Field(0.15, ge=0.01, le=0.5)


class MonitorTask(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    brand: str
    industry: str
    target_questions: list[str]
    frequency: MonitorFrequency
    providers: list[str]
    notify_email: str | None
    change_threshold: float
    is_active: bool
    next_run_at: datetime | None
    last_run_at: datetime | None
    created_at: datetime
    updated_at: datetime


class MentionSnapshot(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    monitor_task_id: str
    run_at: datetime
    mention_rate: float
    mention_count: int
    total_samples: int
    avg_position: float | None
    details: list[dict]
    error_message: str | None
    created_at: datetime


class TrendPoint(BaseModel):
    run_at: datetime
    mention_rate: float
    mention_count: int
    total_samples: int
    avg_position: float | None


class TrendData(BaseModel):
    monitor_id: str
    days: int
    points: list[TrendPoint]
