"""Tests for knowledge base Pydantic schemas."""
import pytest
from pydantic import ValidationError

from app.models.knowledge import (
    KnowledgeBase,
    KnowledgeBaseCreate,
    KnowledgeSearchRequest,
)


class TestKnowledgeBaseCreate:
    def test_min_name(self) -> None:
        with pytest.raises(ValidationError):
            KnowledgeBaseCreate(name="")

    def test_max_description(self) -> None:
        with pytest.raises(ValidationError):
            KnowledgeBaseCreate(name="x", description="x" * 1001)

    def test_valid(self) -> None:
        kb = KnowledgeBaseCreate(name="My KB", description="desc")
        assert kb.name == "My KB"


class TestKnowledgeSearchRequest:
    def test_query_required(self) -> None:
        with pytest.raises(ValidationError):
            KnowledgeSearchRequest(q="")

    def test_limit_bounds(self) -> None:
        with pytest.raises(ValidationError):
            KnowledgeSearchRequest(q="x", limit=0)
        with pytest.raises(ValidationError):
            KnowledgeSearchRequest(q="x", limit=100)
        # Valid
        ok = KnowledgeSearchRequest(q="x", limit=10)
        assert ok.limit == 10
