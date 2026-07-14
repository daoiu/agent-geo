"""Prometheus 指标导出(P1#30 / Task 31)。

指标命名规范: `geo_<area>_<metric>_<unit>`,避免与系统其它指标冲突。

关键指标:
- geo_turn_duration_ms (Histogram): 端到端 turn 延迟
- geo_llm_call_duration_ms (Histogram, label=provider/model): 每次 LLM 调用耗时
- geo_cost_usd_total (Counter, label=provider/model): 累计成本
- geo_tokens_total (Counter, label=type=prompt|completion / provider): token 累计
- geo_human_confirmation_pending (Gauge): 当前 pending HITL 数
- geo_llm_errors_total (Counter, label=error_type): LLM 错误累计

接入:
- `metrics.turn_duration_ms.observe(123)` — 业务代码手动调用
- `GET /metrics` — Prometheus 抓取端点
"""
from __future__ import annotations

from fastapi import APIRouter, Response
from prometheus_client import (
    CONTENT_TYPE_LATEST,
    CollectorRegistry,
    Counter,
    Gauge,
    Histogram,
    generate_latest,
)

# 独立 registry(便于测试隔离)
REGISTRY = CollectorRegistry(auto_describe=True)

# ---------------------------------------------------------------------------
# Histograms(分布/延迟)
# ---------------------------------------------------------------------------

# turn_duration_ms: 端到端 turn 延迟
# buckets 覆盖 100ms - 120s
turn_duration_ms = Histogram(
    "geo_turn_duration_ms",
    "End-to-end agent turn duration in milliseconds",
    buckets=(100, 250, 500, 1000, 2500, 5000, 10_000, 30_000, 60_000, 120_000),
    registry=REGISTRY,
)

# llm_call_duration_ms: 单次 LLM 调用
# buckets 覆盖 100ms - 120s
llm_call_duration_ms = Histogram(
    "geo_llm_call_duration_ms",
    "Single LLM API call duration in milliseconds",
    labelnames=("provider", "model"),
    buckets=(100, 250, 500, 1000, 2500, 5000, 10_000, 30_000, 60_000, 120_000),
    registry=REGISTRY,
)

# ---------------------------------------------------------------------------
# Counters(累计)
# ---------------------------------------------------------------------------

cost_usd_total = Counter(
    "geo_cost_usd_total",
    "Cumulative LLM cost in USD",
    labelnames=("provider", "model"),
    registry=REGISTRY,
)

tokens_total = Counter(
    "geo_tokens_total",
    "Cumulative LLM tokens used",
    labelnames=("type", "provider"),  # type: prompt | completion
    registry=REGISTRY,
)

llm_errors_total = Counter(
    "geo_llm_errors_total",
    "Cumulative LLM errors by type",
    labelnames=("error_type", "provider"),  # rate_limit / timeout / api_error / etc.
    registry=REGISTRY,
)

# ---------------------------------------------------------------------------
# Gauges(瞬时值)
# ---------------------------------------------------------------------------

human_confirmation_pending = Gauge(
    "geo_human_confirmation_pending",
    "Current count of pending human-in-the-loop confirmations",
    registry=REGISTRY,
)


# ---------------------------------------------------------------------------
# FastAPI 路由
# ---------------------------------------------------------------------------

router = APIRouter(tags=["metrics"])


@router.get("/metrics")
def metrics_endpoint() -> Response:
    """Prometheus 抓取端点。

    返回标准 prometheus_client 文本格式:
    ```
    # HELP geo_turn_duration_ms ...
    # TYPE geo_turn_duration_ms histogram
    geo_turn_duration_ms_bucket{le="100"} 0
    ...
    ```
    """
    payload = generate_latest(REGISTRY)
    return Response(content=payload, media_type=CONTENT_TYPE_LATEST)


__all__ = [
    "REGISTRY",
    "router",
    "turn_duration_ms",
    "llm_call_duration_ms",
    "cost_usd_total",
    "tokens_total",
    "llm_errors_total",
    "human_confirmation_pending",
]