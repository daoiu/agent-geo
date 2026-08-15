"""P2#49（Task 39）: 月度成本 dashboard 测试。

目标:
- 聚合 cost events by month/provider/model
- 输出 HTML 含总额、按 provider 分布、按模型 Top N
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest

from evals.cost_dashboard import (
    aggregate_costs,
    render_cost_dashboard,
)


def _make_event(date: str, provider: str, model: str, cost: float, prompt_tokens: int = 100, completion_tokens: int = 50) -> dict:
    return {
        "timestamp": date,
        "provider": provider,
        "model": model,
        "cost_usd": cost,
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
    }


def test_aggregate_costs_groups_by_month() -> None:
    """按月份聚合应正确累加 cost。"""
    events = [
        _make_event("2026-07-01T10:00:00Z", "deepseek", "deepseek-chat", 0.01),
        _make_event("2026-07-15T10:00:00Z", "deepseek", "deepseek-chat", 0.02),
        _make_event("2026-07-20T10:00:00Z", "openai", "gpt-4", 0.50),
        _make_event("2026-06-15T10:00:00Z", "deepseek", "deepseek-chat", 0.03),
    ]
    result = aggregate_costs(events)
    assert "2026-07" in result["by_month"]
    assert "2026-06" in result["by_month"]
    # 2026-07: 0.01 + 0.02 + 0.50 = 0.53
    assert abs(result["by_month"]["2026-07"]["cost_usd"] - 0.53) < 1e-6
    # 2026-06: 0.03
    assert abs(result["by_month"]["2026-06"]["cost_usd"] - 0.03) < 1e-6


def test_aggregate_costs_by_provider() -> None:
    """按 provider 聚合。"""
    events = [
        _make_event("2026-07-01", "deepseek", "ds", 0.01),
        _make_event("2026-07-02", "deepseek", "ds", 0.02),
        _make_event("2026-07-03", "openai", "gpt-4", 0.50),
    ]
    result = aggregate_costs(events)
    assert "deepseek" in result["by_provider"]
    assert "openai" in result["by_provider"]
    assert abs(result["by_provider"]["deepseek"] - 0.03) < 1e-6
    assert abs(result["by_provider"]["openai"] - 0.50) < 1e-6


def test_aggregate_costs_by_model() -> None:
    """按 model 聚合。"""
    events = [
        _make_event("2026-07-01", "openai", "gpt-4", 0.50),
        _make_event("2026-07-02", "openai", "gpt-4", 0.30),
        _make_event("2026-07-03", "openai", "gpt-4o-mini", 0.01),
    ]
    result = aggregate_costs(events)
    assert abs(result["by_model"]["gpt-4"] - 0.80) < 1e-6
    assert abs(result["by_model"]["gpt-4o-mini"] - 0.01) < 1e-6


def test_aggregate_costs_total() -> None:
    """总成本正确。"""
    events = [
        _make_event("2026-07-01", "a", "m1", 0.10),
        _make_event("2026-07-02", "b", "m2", 0.20),
        _make_event("2026-07-03", "c", "m3", 0.30),
    ]
    result = aggregate_costs(events)
    assert abs(result["total_cost_usd"] - 0.60) < 1e-6


def test_aggregate_costs_token_totals() -> None:
    """token 聚合(prompt + completion)。"""
    events = [
        _make_event("2026-07-01", "deepseek", "ds", 0.01, prompt_tokens=100, completion_tokens=50),
        _make_event("2026-07-02", "deepseek", "ds", 0.02, prompt_tokens=200, completion_tokens=100),
    ]
    result = aggregate_costs(events)
    assert result["total_prompt_tokens"] == 300
    assert result["total_completion_tokens"] == 150


def test_aggregate_costs_handles_empty() -> None:
    """空列表应返回全零,不抛。"""
    result = aggregate_costs([])
    assert result["total_cost_usd"] == 0.0
    assert result["total_prompt_tokens"] == 0
    assert result["by_month"] == {}
    assert result["by_provider"] == {}


def test_aggregate_costs_skips_malformed() -> None:
    """坏数据应跳过(不抛)。"""
    events = [
        _make_event("2026-07-01", "deepseek", "ds", 0.01),
        {"timestamp": "not-a-date", "provider": "x", "model": "y", "cost_usd": 0.01},  # 坏日期
        {"provider": "z"},  # 缺字段
    ]
    # 不抛即可(具体行为:跳过坏数据)
    result = aggregate_costs(events)
    # 至少第一条有效
    assert "deepseek" in result["by_provider"]


def test_render_cost_dashboard_creates_html(tmp_path: Path) -> None:
    """渲染 dashboard 必须输出 HTML。"""
    events = [
        _make_event("2026-07-01", "deepseek", "ds", 0.10),
        _make_event("2026-07-02", "openai", "gpt-4", 0.50),
    ]
    out = tmp_path / "cost.html"
    path = render_cost_dashboard(events, out)
    assert path.exists()
    assert path.suffix == ".html"


def test_render_cost_dashboard_shows_total(tmp_path: Path) -> None:
    """dashboard 必须显示总成本。"""
    events = [
        _make_event("2026-07-01", "deepseek", "ds", 0.10),
        _make_event("2026-07-02", "openai", "gpt-4", 0.50),
    ]
    out = tmp_path / "cost.html"
    render_cost_dashboard(events, out)
    html = out.read_text(encoding="utf-8")
    assert "0.60" in html or "60.0" in html


def test_render_cost_dashboard_shows_provider_breakdown(tmp_path: Path) -> None:
    """dashboard 必须显示按 provider 分布。"""
    events = [
        _make_event("2026-07-01", "deepseek", "ds", 0.30),
        _make_event("2026-07-02", "openai", "gpt-4", 0.70),
    ]
    out = tmp_path / "cost.html"
    render_cost_dashboard(events, out)
    html = out.read_text(encoding="utf-8")
    assert "deepseek" in html
    assert "openai" in html


def test_render_cost_dashboard_handles_empty(tmp_path: Path) -> None:
    """空数据应输出占位 HTML。"""
    out = tmp_path / "cost.html"
    path = render_cost_dashboard([], out)
    assert path.exists()
    html = out.read_text(encoding="utf-8")
    assert "<html" in html.lower()
    assert "暂无" in html or "no data" in html.lower()


def test_render_cost_dashboard_includes_chart_js(tmp_path: Path) -> None:
    """dashboard 必须含 Chart.js。"""
    out = tmp_path / "cost.html"
    render_cost_dashboard([_make_event("2026-07-01", "x", "y", 0.1)], out)
    html = out.read_text(encoding="utf-8")
    assert "chart.js" in html.lower() or "chart.umd" in html.lower()