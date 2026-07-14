"""P1#34（Task 35）: 慢查询 dashboard 测试。

目标:
- 从 Prometheus 指标聚合 turn_duration_ms / llm_call_duration_ms
- 输出 P50/P95/P99 + Top 慢查询列表
- 输出静态 HTML(类 eval dashboard)
"""
from __future__ import annotations

from pathlib import Path

import pytest

from evals.slow_query_dashboard import (
    compute_percentiles,
    render_slow_query_dashboard,
)


def _make_durations(values: list[float]) -> list[float]:
    return values


def test_compute_percentiles_basic() -> None:
    """P50/P95/P99 必须正确计算。"""
    durations = list(range(1, 101))  # 1-100, 各 1 次
    p50, p95, p99 = compute_percentiles(durations)
    # 1-100 的中位数约为 50.5
    assert 49 <= p50 <= 52
    # P95 应在 95 左右
    assert 94 <= p95 <= 96
    # P99 应在 99 左右
    assert 98 <= p99 <= 100


def test_compute_percentiles_empty() -> None:
    """空列表应返回 0 不抛。"""
    p50, p95, p99 = compute_percentiles([])
    assert p50 == 0.0
    assert p95 == 0.0
    assert p99 == 0.0


def test_compute_percentiles_single() -> None:
    """单值应返回该值。"""
    p50, p95, p99 = compute_percentiles([42.0])
    assert p50 == 42.0
    assert p95 == 42.0
    assert p99 == 42.0


def test_render_dashboard_creates_html(tmp_path: Path) -> None:
    """render_slow_query_dashboard 必须输出 HTML。"""
    out = tmp_path / "slow.html"
    path = render_slow_query_dashboard(
        turn_durations=[100, 200, 500, 1000, 5000, 30000],
        llm_durations=[50, 100, 200, 1000, 3000],
        slow_queries=[
            {"session_id": "s-1", "turn_ms": 30000, "query": "小米诊断"},
            {"session_id": "s-2", "turn_ms": 25000, "query": "华为搜索"},
        ],
        out_path=out,
    )
    assert path.exists()
    assert path.suffix == ".html"


def test_render_dashboard_shows_percentiles(tmp_path: Path) -> None:
    """dashboard 必须显示 P50/P95/P99。"""
    out = tmp_path / "slow.html"
    render_slow_query_dashboard(
        turn_durations=[100, 200, 300, 400, 500, 600, 700, 800, 900, 1000],
        llm_durations=[],
        slow_queries=[],
        out_path=out,
    )
    html = out.read_text(encoding="utf-8")
    assert "P50" in html
    assert "P95" in html
    assert "P99" in html


def test_render_dashboard_lists_slow_queries(tmp_path: Path) -> None:
    """dashboard 必须列出 Top 慢查询。"""
    out = tmp_path / "slow.html"
    render_slow_query_dashboard(
        turn_durations=[],
        llm_durations=[],
        slow_queries=[
            {"session_id": "s-1", "turn_ms": 30000, "query": "小米品牌诊断"},
            {"session_id": "s-2", "turn_ms": 25000, "query": "华为行业分析"},
        ],
        out_path=out,
    )
    html = out.read_text(encoding="utf-8")
    assert "小米品牌诊断" in html
    assert "华为行业分析" in html
    assert "s-1" in html


def test_render_dashboard_handles_empty_data(tmp_path: Path) -> None:
    """空数据应输出占位 HTML(不崩)。"""
    out = tmp_path / "slow.html"
    path = render_slow_query_dashboard(
        turn_durations=[],
        llm_durations=[],
        slow_queries=[],
        out_path=out,
    )
    assert path.exists()
    html = out.read_text(encoding="utf-8")
    assert "<html" in html.lower()
    assert "暂无" in html or "no data" in html.lower()


def test_render_dashboard_includes_chart_js(tmp_path: Path) -> None:
    """dashboard 必须含 Chart.js(可视化延迟分布)。"""
    out = tmp_path / "slow.html"
    render_slow_query_dashboard(
        turn_durations=[100, 200, 300],
        llm_durations=[],
        slow_queries=[],
        out_path=out,
    )
    html = out.read_text(encoding="utf-8")
    assert "chart.js" in html.lower() or "chart.umd" in html.lower()


def test_render_dashboard_escapes_user_query(tmp_path: Path) -> None:
    """dashboard 必须转义 user query(防 XSS)。"""
    out = tmp_path / "slow.html"
    render_slow_query_dashboard(
        turn_durations=[],
        llm_durations=[],
        slow_queries=[
            {"session_id": "s-xss", "turn_ms": 100, "query": "<script>alert(1)</script>"},
        ],
        out_path=out,
    )
    html = out.read_text(encoding="utf-8")
    # 原始 <script> 不应注入(应被转义为 &lt;script&gt;)
    assert "<script>alert(1)</script>" not in html
    # 转义后的形式应存在
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in html or "alert(1)" not in html.split("<script")[0]