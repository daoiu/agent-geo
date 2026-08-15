"""Tests for monitor Pydantic schemas."""
import pytest
from pydantic import ValidationError

from app.models.monitor import (
    MentionSnapshot,
    MonitorFrequency,
    MonitorTaskCreate,
    TrendData,
    TrendPoint,
)


class TestMonitorTaskCreate:
    def test_min_brand(self) -> None:
        with pytest.raises(ValidationError):
            MonitorTaskCreate(
                name="M", brand="", industry="X",
                target_questions=["q1"], frequency="daily",
            )

    def test_min_one_question(self) -> None:
        with pytest.raises(ValidationError):
            MonitorTaskCreate(
                name="M", brand="X", industry="Y",
                target_questions=[], frequency="daily",
            )

    def test_threshold_bounds(self) -> None:
        with pytest.raises(ValidationError):
            MonitorTaskCreate(
                name="M", brand="X", industry="Y",
                target_questions=["q1"], frequency="daily",
                change_threshold=0.005,  # below min 0.01
            )
        with pytest.raises(ValidationError):
            MonitorTaskCreate(
                name="M", brand="X", industry="Y",
                target_questions=["q1"], frequency="daily",
                change_threshold=0.6,  # above max 0.5
            )

    def test_valid(self) -> None:
        m = MonitorTaskCreate(
            name="监测小米", brand="小米", industry="手机",
            target_questions=["小米14怎么样", "小米vs华为"],
            frequency="daily", providers=["deepseek"],
            notify_email="test@example.com",
        )
        assert m.change_threshold == 0.15  # default


class TestMonitorFrequency:
    def test_enum_values(self) -> None:
        assert MonitorFrequency.HOURLY == "hourly"
        assert MonitorFrequency.DAILY == "daily"
        assert MonitorFrequency.WEEKLY == "weekly"


class TestTrendData:
    def test_empty_points(self) -> None:
        t = TrendData(monitor_id="m1", days=30, points=[])
        assert t.points == []
