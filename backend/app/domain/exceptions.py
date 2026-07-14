"""Custom exceptions for the domain layer."""

import asyncio

import httpx
from openai import APIError, APITimeoutError, RateLimitError
from sqlalchemy.exc import DBAPIError, OperationalError


# Exceptions that should be silently absorbed as "LLM failure" (caller
# marks the work item as errored / falls back). Programming errors
# propagate so we don't hide real bugs.
#
# 阶段 1 P0#6: 从 generator/content_writer.py 上移到 exceptions.py,
# 供 content_writer.py + agent/memory.py 共享(memory 的 LLM 调用路径)。
_LLM_TRANSIENT_EXCEPTIONS: tuple[type[Exception], ...] = (
    asyncio.TimeoutError,
    APITimeoutError,
    RateLimitError,
    APIError,
    httpx.HTTPError,
)


# v0.6+ P1#15（Task 16）：工具执行失败时的 transient 异常分类。
# react_loop 的 except 子句应只捕获这个 tuple，把编程错误（ValueError /
# AttributeError / KeyError / TypeError）向上抛,避免吞掉真实 bug。
#
# 包含：DB 连接/操作错误（OperationalError / DBAPIError）+ 异步超时 +
# HTTP/网络错误（httpx / 内置 ConnectionError）。这些是基础设施层
# 的瞬时问题,工具调用方可以重试或 LLM 可以基于错误信息改方案。
_TOOL_TRANSIENT_EXCEPTIONS: tuple[type[Exception], ...] = (
    asyncio.TimeoutError,
    OperationalError,        # sqlalchemy: 数据库连接断开/超时
    DBAPIError,              # sqlalchemy: 通用 DB API 错误
    httpx.HTTPError,         # httpx: HTTP 请求错误（crawler / 外部 API）
    httpx.RequestError,      # httpx: 请求级错误基类
    ConnectionError,         # 内置: socket / DNS 等
)


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


class KnowledgeError(DomainError):
    """Knowledge base errors."""


class DocumentParseError(KnowledgeError):
    """A document could not be parsed to text."""

    def __init__(self, doc_id: str, file_path: str, reason: str) -> None:
        self.doc_id = doc_id
        self.file_path = file_path
        self.reason = reason
        super().__init__(f"Document {doc_id} parse failed: {reason}")


class ChunkingError(KnowledgeError):
    """Text chunker could not split a document into valid segments."""

    def __init__(self, doc_id: str, reason: str) -> None:
        self.doc_id = doc_id
        self.reason = reason
        super().__init__(f"Chunking failed for {doc_id}: {reason}")


class TaskError(DomainError):
    """Task subsystem errors."""


class TaskNotFoundError(TaskError):
    """Referenced task_id does not exist."""

    def __init__(self, task_id: str) -> None:
        self.task_id = task_id
        super().__init__(f"Task {task_id} not found")


class TaskStateError(TaskError):
    """Task is in a state that doesn't permit the requested action."""

    def __init__(self, task_id: str, current_state: str, attempted: str) -> None:
        self.task_id = task_id
        self.current_state = current_state
        self.attempted = attempted
        super().__init__(
            f"Task {task_id} is {current_state}; cannot {attempted}"
        )


class GenerationError(DomainError):
    """LLM-driven content generation failed."""


class ReviewError(DomainError):
    """Review subsystem errors."""


class PublishError(DomainError):
    """WordPress publish operation failed."""


class NotificationError(DomainError):
    """Email / notification delivery failed."""


class HumanConfirmationRequired(DomainError):
    """写类工具需要人工确认后才能继续执行。

    由 ToolExecutor 在执行 generate_article 等写类工具时抛出，
    携带 message_id（已落库的"待确认"消息）、tool_name 和 arguments，
    ReAct 循环捕获后 yield SSE 事件 human_confirmation_required 并暂停。
    """

    def __init__(self, message_id: str, tool_name: str, arguments: dict) -> None:
        self.message_id = message_id
        self.tool_name = tool_name
        self.arguments = arguments
        super().__init__(
            f"Tool {tool_name} requires human confirmation "
            f"(message_id={message_id})"
        )
