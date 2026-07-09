"""Tests for Pydantic schema validation."""
import pytest
from pydantic import ValidationError

from app.models.schemas import (
    DiagnosisRequest,
    DimensionScore,
    TaskStatus,
)


class TestDiagnosisRequest:
    def test_valid_request_passes(self) -> None:
        req = DiagnosisRequest(
            brand_name="小米",
            industry="手机",
            official_url="https://www.mi.com",
            target_questions=["小米手机怎么样", "小米14值得买吗", "小米vs华为"],
        )
        assert req.brand_name == "小米"
        assert len(req.target_questions) == 3
        assert req.competitors == []  # default

    def test_url_must_be_valid(self) -> None:
        with pytest.raises(ValidationError):
            DiagnosisRequest(
                brand_name="x",
                industry="y",
                official_url="not-a-url",
                target_questions=["q1", "q2", "q3"],
            )

    def test_min_three_questions(self) -> None:
        with pytest.raises(ValidationError):
            DiagnosisRequest(
                brand_name="x",
                industry="y",
                official_url="https://example.com",
                target_questions=["only one"],
            )


class TestDimensionScore:
    def test_score_bounds(self) -> None:
        DimensionScore(name="权威度", score=8.5, weight=0.25, evidence=["x"])
        with pytest.raises(ValidationError):
            DimensionScore(name="x", score=11.0, weight=0.25, evidence=[])


class TestTaskStatus:
    def test_enum_values(self) -> None:
        assert TaskStatus.PENDING == "pending"
        assert TaskStatus.COMPLETED == "completed"
        assert TaskStatus.FAILED == "failed"
