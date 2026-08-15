"""故障注入工具(P2#31 / Task 40)。

Dev / test 工具:在 LLM 调用 / 工具调用路径中模拟各种故障。

安全:
- 默认禁用(必须显式 enable),防止生产误用
- 可在测试中通过 env var GEO_FAULT_INJECTION=1 启用

使用:
    injector = FaultInjector()
    injector.enable()
    injector.add_rule(
        match_fn=lambda ctx: ctx.get("tool_name") == "search_knowledge",
        fault_type=FaultType.TIMEOUT,
        probability=0.5,
    )
    injector.maybe_inject({"tool_name": "search_knowledge"})
"""
from __future__ import annotations

import asyncio
import logging
import os
import random
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Awaitable, Callable

from .fallback import PermanentError, TransientError

logger = logging.getLogger(__name__)


class FaultType(str, Enum):
    RATE_LIMIT = "rate_limit"  # 429 → TransientError
    TIMEOUT = "timeout"  # 超时 → asyncio.TimeoutError → TransientError
    AUTH_ERROR = "auth_error"  # 401 → PermanentError
    CONTENT_FILTER = "content_filter"  # 内容审查 → PermanentError
    NETWORK = "network"  # 连接失败 → TransientError
    SERVER_ERROR = "server_error"  # 5xx → TransientError


# FaultType → 异常类映射
_FAULT_EXCEPTIONS: dict[FaultType, type[Exception] | Callable[[], Exception]] = {
    FaultType.RATE_LIMIT: lambda: TransientError("injected: rate limit"),
    FaultType.TIMEOUT: lambda: asyncio.TimeoutError("injected: timeout"),
    FaultType.AUTH_ERROR: lambda: PermanentError("injected: auth failed"),
    FaultType.CONTENT_FILTER: lambda: PermanentError("injected: content filter"),
    FaultType.NETWORK: lambda: TransientError("injected: network failure"),
    FaultType.SERVER_ERROR: lambda: TransientError("injected: server 5xx"),
}


@dataclass
class FaultRule:
    match_fn: Callable[[dict], bool]
    fault_type: FaultType
    probability: float = 1.0
    description: str = ""


@dataclass
class FaultInjector:
    """故障注入器。

    默认禁用。enable() 后规则生效。
    """

    enabled: bool = False
    rules: list[FaultRule] = field(default_factory=list)
    injection_count: int = 0

    def enable(self) -> None:
        self.enabled = True
        logger.warning("[fault_injector] ENABLED — 生产环境请勿使用")

    def disable(self) -> None:
        self.enabled = False

    def add_rule(
        self,
        match_fn: Callable[[dict], bool],
        fault_type: FaultType,
        probability: float = 1.0,
        description: str = "",
    ) -> None:
        self.rules.append(
            FaultRule(
                match_fn=match_fn,
                fault_type=fault_type,
                probability=probability,
                description=description,
            )
        )

    def maybe_inject(self, context: dict[str, Any]) -> None:
        """根据 context 检查所有规则,首个匹配的规则可能抛异常。"""
        if not self.enabled:
            return

        for rule in self.rules:
            if not rule.match_fn(context):
                continue
            # 命中规则,按概率决定是否抛
            if random.random() > rule.probability:
                continue
            self.injection_count += 1
            logger.warning(
                f"[fault_injector] injecting {rule.fault_type.value} "
                f"(rule={rule.description!r}, count={self.injection_count})"
            )
            exc_factory = _FAULT_EXCEPTIONS.get(rule.fault_type)
            if exc_factory is None:
                raise RuntimeError(f"unknown fault type: {rule.fault_type}")
            raise exc_factory()


def inject_fault_into_call(
    call_fn: Callable[..., Awaitable],
    injector: FaultInjector,
    context: dict[str, Any] | None = None,
):
    """包装 async 函数,在调用前注入故障检查。"""
    ctx = context or {}

    async def _wrapped(*args, **kwargs):
        injector.maybe_inject(ctx)
        return await call_fn(*args, **kwargs)

    return _wrapped


# 全局默认 injector(供装饰器模式使用)
_global_injector = FaultInjector()


def get_global_injector() -> FaultInjector:
    return _global_injector


# 检查 env var(供 main.py 启动时自动启用)
def maybe_enable_from_env() -> bool:
    """如果 GEO_FAULT_INJECTION=1,启用全局 injector。返回是否启用。"""
    if os.environ.get("GEO_FAULT_INJECTION") == "1":
        _global_injector.enable()
        return True
    return False


__all__ = [
    "FaultType",
    "FaultInjector",
    "FaultRule",
    "inject_fault_into_call",
    "get_global_injector",
    "maybe_enable_from_env",
]