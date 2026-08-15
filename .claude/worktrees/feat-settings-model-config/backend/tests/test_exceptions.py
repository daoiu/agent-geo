"""Tests for domain exception hierarchy."""
import pytest

from app.domain.exceptions import CrawlError, DomainError, LlmError, RenderError


class TestHierarchy:
    def test_all_inherit_from_domain_error(self) -> None:
        assert issubclass(CrawlError, DomainError)
        assert issubclass(LlmError, DomainError)
        assert issubclass(RenderError, DomainError)


class TestCrawlError:
    def test_carries_url_and_reason(self) -> None:
        err = CrawlError(reason="DNS lookup failed", url="https://x.example")
        assert err.reason == "DNS lookup failed"
        assert err.url == "https://x.example"
        assert "DNS lookup failed" in str(err)


class TestLlmError:
    def test_retryable_flag(self) -> None:
        retryable = LlmError(provider="deepseek", message="rate limit", retryable=True)
        permanent = LlmError(provider="deepseek", message="bad key", retryable=False)
        assert retryable.retryable is True
        assert permanent.retryable is False
        with pytest.raises(LlmError):
            raise retryable
