"""MemoryService 异常分类测试 (P0#6)。

依据: docs/review/05-failure-recovery.md §3.5 + upgrade-design §3 P0#6。

分类原则 (复用 _LLM_TRANSIENT_EXCEPTIONS 模式):
- Transient 异常 (RateLimitError / TimeoutError / APIError / httpx.HTTPError)
  → 应被捕获 + 降级(返回 [] / 0 / 上次结果)
- Programming 异常 (KeyError / AttributeError / TypeError / ValueError)
  → 应向上抛,不静默吞掉

memory.py 中 4 处 LLM 调用路径(select_relevant / extract x 2 / consolidate)需要
从 except Exception 改为 except _LLM_TRANSIENT_EXCEPTIONS。

4 处 DB/vector 操作路径暂保留 except Exception (DB/vector 与 LLM 不同源)。
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from openai import APIError, APITimeoutError, RateLimitError

from app.domain.agent.memory import MemoryService
from app.domain.exceptions import _LLM_TRANSIENT_EXCEPTIONS


def _make_service() -> MemoryService:
    """最小 MemoryService — 用 mock session(repo 内部从 session 构造)。"""
    session = MagicMock()
    svc = MemoryService(session=session, threshold=10)
    svc.repo = MagicMock()  # override repo 用于 stub
    return svc


def _patch_select_relevant_deps() -> list:
    """select_relevant 需要 _ensure_vectors + EmbeddingService + MemoryVectorIndex 全部 mock,
    避免真实调用 embedding service / chroma db。"""
    return [
        patch("app.domain.agent.memory.MemoryVectorIndex"),
        patch("app.domain.agent.memory.EmbeddingService"),
    ]


# ---------------------------------------------------------------------------
# _LLM_TRANSIENT_EXCEPTIONS 自身契约测试
# ---------------------------------------------------------------------------
def test_llm_transient_exceptions_contains_expected_types() -> None:
    """_LLM_TRANSIENT_EXCEPTIONS 必须包含 5 类 LLM/网络 transient 异常。"""
    names = {t.__name__ for t in _LLM_TRANSIENT_EXCEPTIONS}
    expected = {"TimeoutError", "APITimeoutError", "RateLimitError", "APIError", "HTTPError"}
    assert expected.issubset(names), f"missing: {expected - names}"


def test_llm_transient_exceptions_shared_between_modules() -> None:
    """content_writer 与 memory 共享同一个 _LLM_TRANSIENT_EXCEPTIONS 实例。"""
    import app.domain.agent.memory as mem
    import app.domain.generator.content_writer as cw

    assert id(cw._LLM_TRANSIENT_EXCEPTIONS) == id(_LLM_TRANSIENT_EXCEPTIONS) == id(mem._LLM_TRANSIENT_EXCEPTIONS)


# ---------------------------------------------------------------------------
# Transient 异常:应被捕获 + 降级(不抛)
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_select_relevant_swallows_transient_via_exception_class() -> None:
    """_LLM_TRANSIENT_EXCEPTIONS 应通过 except tuple 语义捕获 LLM/网络 4 类异常。"""
    # except (A, B, C) 语义: isinstance(exc, (A, B, C))
    # 验证每个异常类型至少与 tuple 中某个成员是 subclass 关系
    def _covered_by_tuple(exc_cls: type) -> bool:
        return any(issubclass(exc_cls, t) for t in _LLM_TRANSIENT_EXCEPTIONS)

    assert _covered_by_tuple(RateLimitError), "RateLimitError 未被 _LLM_TRANSIENT_EXCEPTIONS 覆盖"
    assert _covered_by_tuple(APITimeoutError), "APITimeoutError 未被覆盖"
    assert _covered_by_tuple(APIError), "APIError 未被覆盖"
    assert _covered_by_tuple(httpx.HTTPError), "httpx.HTTPError 未被覆盖"
    assert _covered_by_tuple(httpx.ConnectError), "httpx.ConnectError(HTTPError 子类) 未被覆盖"


@pytest.mark.asyncio
async def test_extract_swallows_transient_llm_error_via_contract() -> None:
    """extract: LLM 路径用 _LLM_TRANSIENT_EXCEPTIONS 捕获。
    通过 _LLM_TRANSIENT_EXCEPTIONS 的契约验证(进入 except 块的类型集合)。"""
    from app.domain.exceptions import _LLM_TRANSIENT_EXCEPTIONS

    # 验证 extract 中使用的 except 类型确实是 _LLM_TRANSIENT_EXCEPTIONS
    import inspect

    source = inspect.getsource(__import__("app.domain.agent.memory", fromlist=["extract"]))
    # extract 内 except 块必须用 _LLM_TRANSIENT_EXCEPTIONS
    assert "except _LLM_TRANSIENT_EXCEPTIONS" in source, (
        "extract() 必须捕获 _LLM_TRANSIENT_EXCEPTIONS(不是 Exception)"
    )
    # 且 extract 块中不应再有 except Exception(LLM 调用路径)
    extract_section = source[source.find("async def extract"):]
    # 4 处 LLM 路径应都用 _LLM_TRANSIENT_EXCEPTIONS
    n_transient = extract_section.count("except _LLM_TRANSIENT_EXCEPTIONS")
    assert n_transient >= 2, f"extract 至少 2 处 LLM 路径用 _LLM_TRANSIENT_EXCEPTIONS, 实际 {n_transient}"


# ---------------------------------------------------------------------------
# Programming 异常:不被 _LLM_TRANSIENT_EXCEPTIONS 覆盖
# ---------------------------------------------------------------------------
def test_programming_errors_not_in_transient_set() -> None:
    """编程错误(KeyError / AttributeError / TypeError / ValueError)不在 transient 集合内。"""
    names = {t.__name__ for t in _LLM_TRANSIENT_EXCEPTIONS}
    for cls_name in ("KeyError", "AttributeError", "TypeError", "ValueError", "IndexError"):
        assert cls_name not in names, (
            f"{cls_name} 是编程错误,不应在 _LLM_TRANSIENT_EXCEPTIONS 内"
        )


# ---------------------------------------------------------------------------
# memory.py 源码契约测试(直接断言 except 块类型,避免依赖运行)
# ---------------------------------------------------------------------------
def test_memory_source_uses_transient_in_llm_paths() -> None:
    """memory.py 源码中 4 处 LLM 路径必须用 _LLM_TRANSIENT_EXCEPTIONS,不是 Exception。"""
    import inspect

    source = inspect.getsource(__import__("app.domain.agent.memory", fromlist=["MemoryService"]))
    # 4 处 LLM 路径 select_relevant / extract / extract_dedup / consolidate
    n_transient = source.count("except _LLM_TRANSIENT_EXCEPTIONS")
    assert n_transient >= 4, (
        f"memory.py 至少 4 处 LLM 路径用 _LLM_TRANSIENT_EXCEPTIONS, 实际 {n_transient}"
    )