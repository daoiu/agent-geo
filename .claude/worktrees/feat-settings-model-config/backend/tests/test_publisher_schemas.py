"""Tests for publisher Pydantic schemas."""
import pytest
from pydantic import ValidationError

from app.models.publisher import (
    PublishJobCreate,
    PublishJobStatus,
    PublisherConfigCreate,
)


class TestPublisherConfigCreate:
    def test_min_name(self) -> None:
        with pytest.raises(ValidationError):
            PublisherConfigCreate(
                name="", site_url="https://example.com",
                username="u", app_password="short",
            )

    def test_min_app_password(self) -> None:
        with pytest.raises(ValidationError):
            PublisherConfigCreate(
                name="X", site_url="https://example.com",
                username="u", app_password="short",
            )

    def test_valid(self) -> None:
        c = PublisherConfigCreate(
            name="主站", site_url="https://example.com",
            username="admin", app_password="abcdefghijklmnop",
        )
        assert c.name == "主站"


class TestPublishJobCreate:
    def test_valid(self) -> None:
        j = PublishJobCreate(article_id="a1", config_id="pc1")
        assert j.title_override is None

    def test_with_title_override(self) -> None:
        j = PublishJobCreate(article_id="a1", config_id="pc1", title_override="新标题")
        assert j.title_override == "新标题"


class TestPublishJobStatus:
    def test_enum_values(self) -> None:
        assert PublishJobStatus.PENDING == "pending"
        assert PublishJobStatus.SUCCESS == "success"
        assert PublishJobStatus.FAILED == "failed"
