"""Custom exceptions for the domain layer."""


class DomainError(Exception):
    """Base for all domain-level errors."""


class CrawlError(DomainError):
    """Website could not be crawled to a usable state."""

    def __init__(self, reason: str, url: str) -> None:
        self.reason = reason
        self.url = url
        super().__init__(f"Crawl failed for {url}: {reason}")


class LlmError(DomainError):
    """LLM call failed."""

    def __init__(self, provider: str, message: str, retryable: bool) -> None:
        self.provider = provider
        self.retryable = retryable
        super().__init__(f"LLM error ({provider}): {message}")


class ScoreError(DomainError):
    """Scoring engine encountered invalid data."""


class RenderError(DomainError):
    """PDF/HTML rendering failed."""
