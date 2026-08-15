"""P1#30（Task 31）: Prometheus 指标导出验证。

目标:
- /metrics 端点暴露 prometheus_client 标准格式
- 关键指标: turn_duration / llm_call_duration / cost / token / hitl pending / errors
- 指标能被 Prometheus 抓取(generate_latest() 输出可解析)
- FastAPI /metrics 路由注册
"""
from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from prometheus_client import generate_latest


def _all_metrics():
    """从自定义 REGISTRY 生成全部指标(避免被全局 REGISTRY 的 python_* 污染)。"""
    from app.core.metrics import REGISTRY
    return generate_latest(REGISTRY).decode("utf-8")


def test_metrics_module_exports_required_metrics():
    """metrics 模块必须导出关键指标:turn_duration / llm_duration / cost / tokens / hitl / errors。"""
    from app.core import metrics

    required = [
        "turn_duration_ms",
        "llm_call_duration_ms",
        "cost_usd_total",
        "tokens_total",
        "human_confirmation_pending",
        "llm_errors_total",
    ]
    for name in required:
        assert hasattr(metrics, name), f"missing metric: {name}"


def test_metrics_endpoint_returns_prometheus_format():
    """FastAPI /metrics 端点必须返回 prometheus_client 标准格式。"""
    from app.core.metrics import router

    app = FastAPI()
    app.include_router(router)
    client = TestClient(app)
    resp = client.get("/metrics")
    assert resp.status_code == 200
    text = resp.text
    assert "# HELP" in text
    assert "# TYPE" in text
    assert "text/plain" in resp.headers.get("content-type", "")


def test_metrics_endpoint_includes_geo_namespace():
    """指标名应以 'geo_' 前缀。"""
    from app.core.metrics import router

    app = FastAPI()
    app.include_router(router)
    client = TestClient(app)
    resp = client.get("/metrics")
    assert "geo_" in resp.text, f"missing 'geo_' namespace; got sample: {resp.text[:500]}"


def test_turn_duration_histogram_observes_value():
    """turn_duration_ms histogram 应能记录观测值。"""
    from app.core import metrics

    metrics.turn_duration_ms.observe(123.0)
    text = _all_metrics()
    assert "geo_turn_duration_ms" in text


def test_cost_counter_increments():
    """cost_usd_total counter 应能累加。"""
    from app.core import metrics

    metrics.cost_usd_total.labels(provider="openai", model="gpt-4").inc(0.05)
    text = _all_metrics()
    assert "cost_usd_total" in text
    assert "openai" in text
    assert "gpt-4" in text


def test_tokens_counter_has_label():
    """tokens_total counter 必须有 type label (prompt/completion)。"""
    from app.core import metrics

    metrics.tokens_total.labels(type="prompt", provider="openai").inc(100)
    metrics.tokens_total.labels(type="completion", provider="openai").inc(50)
    text = _all_metrics()
    assert "prompt" in text
    assert "completion" in text


def test_hitl_pending_gauge_sets_value():
    """human_confirmation_pending gauge 必须能设值。"""
    from app.core import metrics

    metrics.human_confirmation_pending.set(3)
    text = _all_metrics()
    assert "human_confirmation_pending" in text
    assert "3.0" in text


def test_llm_errors_counter_labels():
    """llm_errors_total counter 必须有 error_type + provider label。"""
    from app.core import metrics

    metrics.llm_errors_total.labels(error_type="rate_limit", provider="openai").inc()
    metrics.llm_errors_total.labels(error_type="timeout", provider="openai").inc(2)
    text = _all_metrics()
    assert "rate_limit" in text
    assert "timeout" in text


def test_metrics_endpoint_works_when_app_initialized():
    """主 FastAPI app 应注册 /metrics 路由。"""
    from app.main import app

    client = TestClient(app)
    resp = client.get("/metrics")
    assert resp.status_code == 200
    assert "geo_" in resp.text or "# HELP" in resp.text