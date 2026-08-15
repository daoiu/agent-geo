"""P2#31（Task 40）: 故障注入工具测试。

目标:
- 提供 dev/test 故障注入器
- 支持多种故障类型: rate_limit / timeout / auth / content_filter / network
- 可注入到 LLM 调用或工具调用路径
- 注入器在生产自动禁用(显式 opt-in)
"""
from __future__ import annotations

import asyncio
import os
from unittest.mock import patch

import pytest

from app.core.fault_injector import (
    FaultInjector,
    FaultType,
    inject_fault_into_call,
)


def test_fault_type_enum_values():
    """FaultType 必须含 5 类以上。"""
    types = {t.value for t in FaultType}
    assert "rate_limit" in types
    assert "timeout" in types
    assert "auth_error" in types
    assert "network" in types


def test_fault_injector_disabled_by_default():
    """FaultInjector 默认禁用(防止生产误用)。"""
    from app.core.fault_injector import FaultInjector

    injector = FaultInjector()
    assert injector.enabled is False


def test_fault_injector_enable_explicit():
    """必须显式 enable。"""
    from app.core.fault_injector import FaultInjector

    injector = FaultInjector()
    injector.enable()
    assert injector.enabled is True


def test_fault_injector_program_rule():
    """可编程注入规则:type + match + action。"""
    from app.core.fault_injector import FaultInjector, FaultType

    injector = FaultInjector()
    injector.enable()
    injector.add_rule(
        match_fn=lambda ctx: "search_knowledge" in ctx.get("tool_name", ""),
        fault_type=FaultType.TIMEOUT,
        probability=1.0,
    )
    # 匹配时抛
    with pytest.raises(asyncio.TimeoutError):
        injector.maybe_inject({"tool_name": "search_knowledge"})
    # 不匹配时不抛
    injector.maybe_inject({"tool_name": "other"})  # 不抛


def test_fault_injector_respects_probability():
    """probability=0 时永不触发。"""
    from app.core.fault_injector import FaultInjector, FaultType

    injector = FaultInjector()
    injector.enable()
    injector.add_rule(
        match_fn=lambda ctx: True,
        fault_type=FaultType.RATE_LIMIT,
        probability=0.0,
    )
    # 跑 100 次都不抛
    for _ in range(100):
        injector.maybe_inject({})


def test_fault_injector_throws_correct_exception_for_type():
    """不同 fault_type 抛不同异常类。"""
    from app.core.fault_injector import FaultInjector, FaultType
    from app.core.fallback import TransientError, PermanentError

    injector = FaultInjector()
    injector.enable()
    injector.add_rule(
        match_fn=lambda ctx: True,
        fault_type=FaultType.RATE_LIMIT,
        probability=1.0,
    )
    with pytest.raises(TransientError):
        injector.maybe_inject({})

    injector2 = FaultInjector()
    injector2.enable()
    injector2.add_rule(
        match_fn=lambda ctx: True,
        fault_type=FaultType.AUTH_ERROR,
        probability=1.0,
    )
    with pytest.raises(PermanentError):
        injector2.maybe_inject({})


def test_inject_fault_into_call_helper():
    """inject_fault_into_call 必须包装函数 + 注入故障。"""
    from app.core.fault_injector import FaultInjector, FaultType

    injector = FaultInjector()
    injector.enable()
    injector.add_rule(
        match_fn=lambda ctx: True,
        fault_type=FaultType.TIMEOUT,
        probability=1.0,
    )

    async def fake_call():
        return "ok"

    wrapped = inject_fault_into_call(fake_call, injector, context={"x": 1})
    with pytest.raises(asyncio.TimeoutError):
        asyncio.run(wrapped())


def test_fault_injector_can_be_disabled_at_runtime():
    """disable() 后注入器不应抛。"""
    from app.core.fault_injector import FaultInjector, FaultType

    injector = FaultInjector()
    injector.enable()
    injector.add_rule(
        match_fn=lambda ctx: True,
        fault_type=FaultType.RATE_LIMIT,
        probability=1.0,
    )
    injector.disable()
    # disable 后不抛
    injector.maybe_inject({})


def test_fault_injector_logs_injection():
    """注入应被记录(便于调试)。"""
    from app.core.fault_injector import FaultInjector, FaultType

    injector = FaultInjector()
    injector.enable()
    injector.add_rule(
        match_fn=lambda ctx: True,
        fault_type=FaultType.RATE_LIMIT,
        probability=1.0,
    )
    with pytest.raises(Exception):
        injector.maybe_inject({"tool": "x"})
    # 应至少记录一次注入
    assert injector.injection_count >= 1


def test_fault_injector_requires_enable_to_inject():
    """禁用时 even with rule, 不抛。"""
    from app.core.fault_injector import FaultInjector, FaultType

    injector = FaultInjector()
    # 不 enable,即使有规则也不抛
    injector.add_rule(
        match_fn=lambda ctx: True,
        fault_type=FaultType.RATE_LIMIT,
        probability=1.0,
    )
    injector.maybe_inject({})  # 不抛