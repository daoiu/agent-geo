"""v0.6+ P1#17（Task 18）：Sentry 异常聚合接入。

设计：
- init_sentry(dsn, ...) — 手动传参初始化
- init_sentry_from_settings() — 从 SENTRY_DSN env 读,缺失时静默 no-op
- DSN 缺失/为空时整个函数静默 no-op,不抛异常（per handoff §应急方案）
- 默认 traces_sample_rate=0.1（低采样,避免性能影响）
"""
from __future__ import annotations

import os

import sentry_sdk


_DEFAULT_TRACES_SAMPLE_RATE = 0.1
_DEFAULT_ENVIRONMENT = "development"
_DEFAULT_RELEASE = "geo2@unknown"


def init_sentry(
    dsn: str | None,
    *,
    environment: str = _DEFAULT_ENVIRONMENT,
    release: str = _DEFAULT_RELEASE,
    traces_sample_rate: float = _DEFAULT_TRACES_SAMPLE_RATE,
) -> bool:
    """初始化 Sentry。

    Returns:
        True 表示已初始化,False 表示 DSN 缺失未初始化。

    行为：
    - dsn 为 None / 空字符串 / 全空白 → 静默返回 False,不抛
    - dsn 非空 → 调 sentry_sdk.init,返回 True
    """
    if not dsn or not dsn.strip():
        return False

    sentry_sdk.init(
        dsn=dsn.strip(),
        environment=environment,
        release=release,
        traces_sample_rate=traces_sample_rate,
    )
    return True


def init_sentry_from_settings() -> bool:
    """从环境变量读 SENTRY_DSN 初始化 Sentry。

    缺失/为空时静默 no-op。便于 main.py 启动时无脑调用,不影响本地开发。
    """
    dsn = os.environ.get("SENTRY_DSN", "")
    return init_sentry(
        dsn=dsn,
        environment=os.environ.get("SENTRY_ENVIRONMENT", _DEFAULT_ENVIRONMENT),
        release=os.environ.get("SENTRY_RELEASE", _DEFAULT_RELEASE),
        traces_sample_rate=float(
            os.environ.get("SENTRY_TRACES_SAMPLE_RATE", str(_DEFAULT_TRACES_SAMPLE_RATE))
        ),
    )