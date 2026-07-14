"""Fallback 策略(P2#51 / Task 37)。

核心概念:
- TransientError: 可恢复的瞬时错误(超时/rate limit/5xx/network)
- PermanentError: 不可恢复的永久错误(401/403/参数校验失败)

策略:
- 遇到 TransientError → 切到下一个 provider
- 遇到 PermanentError → 立即抛出,不切

辅助:
- call_with_fallback(call_fn, chain, *args, **kwargs):
    依次尝试 chain 中每个 provider,call_fn(provider, *args, **kwargs)
    第一个成功返回;若全部失败,抛最后一个异常(包含尝试历史)
"""
from __future__ import annotations

import asyncio
import os
from typing import Awaitable, Callable, Iterable


class TransientError(Exception):
    """可恢复错误: rate limit / timeout / 5xx / network。"""


class PermanentError(Exception):
    """不可恢复错误: auth / 参数校验 / 4xx client error。"""


def _provider_has_key(provider: str) -> bool:
    """检查 provider 是否配置了 API key。"""
    env_map = {
        "deepseek": "DEEPSEEK_API_KEY",
        "kimi": "KIMI_API_KEY",
        "openai": "OPENAI_API_KEY",
        "minimax": "MINIMAX_API_KEY",
    }
    env_name = env_map.get(provider, f"{provider.upper()}_API_KEY")
    return bool(os.environ.get(env_name))


def _eligible_providers(chain: Iterable[str]) -> list[str]:
    """过滤出有 API key 的 provider。无 key 的跳过(避免运行时 auth 失败)。"""
    eligible = []
    for p in chain:
        if _provider_has_key(p):
            eligible.append(p)
    # 如果全部无 key(测试场景),返回原 chain 不抛
    if not eligible:
        return list(chain)
    return eligible


async def call_with_fallback(
    call_fn: Callable[..., Awaitable],
    chain: list[str],
    *args,
    **kwargs,
):
    """依次尝试 chain 中每个 provider,成功即返回;全失败抛最后异常。

    call_fn 签名: async def call_fn(provider: str, *args, **kwargs) -> Any
    chain 中 provider 应按优先级排序(主 provider 在前)
    """
    eligible = _eligible_providers(chain)
    last_exc: Exception | None = None
    attempts: list[tuple[str, Exception]] = []

    for provider in eligible:
        try:
            return await call_fn(provider, *args, **kwargs)
        except PermanentError:
            # 永久错误不切换,直接抛
            raise
        except TransientError as exc:
            attempts.append((provider, exc))
            last_exc = exc
            # 记录 metric
            try:
                from app.core import metrics
                metrics.llm_errors_total.labels(
                    error_type="transient", provider=provider
                ).inc()
            except Exception:
                pass
            continue
        except Exception as exc:
            # 未知错误:不切换,直接抛(防止隐藏 bug)
            raise

    # 全部失败
    if last_exc is not None:
        # 增强异常信息(包含尝试历史)
        history = ", ".join(f"{p}: {type(e).__name__}" for p, e in attempts)
        if len(attempts) > 1:
            raise TransientError(
                f"All providers in fallback chain failed ({history}): {last_exc}"
            ) from last_exc
        raise last_exc
    raise RuntimeError(f"call_with_fallback: empty chain {chain}")


__all__ = [
    "TransientError",
    "PermanentError",
    "call_with_fallback",
]