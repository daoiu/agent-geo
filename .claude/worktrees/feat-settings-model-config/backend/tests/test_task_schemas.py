"""Tests for task/article/review Pydantic schemas."""
import pytest
from pydantic import ValidationError

from app.models.task import (
    Article,
    ReviewAction,
    ReviewStatus,
    Style,
    TaskCreate,
    TaskStatus,
)


class TestTaskCreate:
    def test_min_topic(self) -> None:
        with pytest.raises(ValidationError):
            TaskCreate(
                name="T", kb_id="kb1", topic="短",
                article_count=1, style="neutral",
            )

    def test_article_count_bounds(self) -> None:
        with pytest.raises(ValidationError):
            TaskCreate(name="T", kb_id="kb1", topic="足够长的主题", article_count=0)
        with pytest.raises(ValidationError):
            TaskCreate(
                name="T", kb_id="kb1", topic="足够长的主题",
                article_count=21, style="neutral",
            )

    def test_target_length_bounds(self) -> None:
        with pytest.raises(ValidationError):
            TaskCreate(
                name="T", kb_id="kb1", topic="足够长的主题",
                article_count=1, style="neutral", target_length=100,
            )
        # Valid
        ok = TaskCreate(
            name="T", kb_id="kb1", topic="足够长的主题",
            article_count=1, style="neutral", target_length=2000,
        )
        assert ok.target_length == 2000

    def test_valid_task(self) -> None:
        t = TaskCreate(
            name="My Task", kb_id="kb1", brand="Brand",
            topic="生成关于产品的文章", keywords=["k1", "k2"],
            article_count=3, style="professional",
        )
        assert t.article_count == 3
        assert t.style == Style.PROFESSIONAL
        assert t.brand == "Brand"


class TestReviewAction:
    def test_reject_requires_note(self) -> None:
        # Note is optional in schema; API endpoint enforces for reject specifically
        a = ReviewAction(note=None)
        assert a.note is None


class TestEnums:
    def test_status_values(self) -> None:
        assert TaskStatus.PENDING == "pending"
        assert TaskStatus.RUNNING == "running"
        assert TaskStatus.COMPLETED == "completed"

    def test_review_status_values(self) -> None:
        assert ReviewStatus.PENDING == "pending"
        assert ReviewStatus.APPROVED == "approved"
        assert ReviewStatus.REJECTED == "rejected"
