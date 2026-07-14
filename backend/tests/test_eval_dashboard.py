"""P1#29（Task 30）: 评测可视化面板验证。

目标:
- 输出静态 HTML(无服务端依赖)
- 含 Chart.js(CDN 引入)
- 展示 pass rate / by_category / 趋势
- 多报告支持趋势对比
"""
from __future__ import annotations

from pathlib import Path

import pytest

from evals.dashboard import render_dashboard


def _make_report(label: str, pass_rate: float, total: int = 30, by_cat: dict | None = None) -> dict:
    """构造一个伪报告 dict。"""
    return {
        "label": label,
        "total": total,
        "pass": int(total * pass_rate),
        "pass_rate": pass_rate,
        "avg_score": 0.7,
        "avg_latency_ms": 100.0,
        "by_category": by_cat or {
            "normal": {"total": 8, "pass": 8, "pass_rate": 1.0},
            "boundary": {"total": 6, "pass": 3, "pass_rate": 0.5},
            "missing": {"total": 6, "pass": 2, "pass_rate": 0.33},
            "induction": {"total": 5, "pass": 4, "pass_rate": 0.8},
            "refusal": {"total": 5, "pass": 5, "pass_rate": 1.0},
        },
        "details": [],
        "note": f"fake {label}",
    }


def test_render_dashboard_creates_html_file(tmp_path: Path):
    """render_dashboard 必须输出 HTML 文件。"""
    out = tmp_path / "dashboard.html"
    reports = [_make_report("v1", 0.5)]
    path = render_dashboard(reports, out)
    assert path.exists()
    assert path.suffix == ".html"


def test_render_dashboard_contains_pass_rate(tmp_path: Path):
    """HTML 必须显示 pass rate(摘要卡片 + Chart.js 数据)。"""
    out = tmp_path / "dashboard.html"
    reports = [_make_report("v1", 0.567)]
    path = render_dashboard(reports, out)
    html = path.read_text(encoding="utf-8")
    # 摘要卡片含 0.567
    assert "56.7%" in html or "0.567" in html
    # Chart.js 数据点含 0.567
    assert "0.567" in html


def test_render_dashboard_includes_chart_js(tmp_path: Path):
    """HTML 必须通过 CDN 引入 Chart.js。"""
    out = tmp_path / "dashboard.html"
    reports = [_make_report("v1", 0.5)]
    path = render_dashboard(reports, out)
    html = path.read_text(encoding="utf-8")
    assert "chart.js" in html.lower() or "chart.min.js" in html.lower()


def test_render_dashboard_handles_multiple_reports(tmp_path: Path):
    """多份报告应展示趋势(折线图)。"""
    out = tmp_path / "dashboard.html"
    reports = [
        _make_report("v1", 0.4),
        _make_report("v2", 0.55),
        _make_report("v3", 0.72),
    ]
    path = render_dashboard(reports, out)
    html = path.read_text(encoding="utf-8")
    # 必须含三个版本的 pass rate
    assert "40.0%" in html
    assert "55.0%" in html or "0.55" in html
    assert "72.0%" in html or "0.72" in html


def test_render_dashboard_shows_by_category_chart(tmp_path: Path):
    """HTML 必须含按类别 pass rate 的图。"""
    out = tmp_path / "dashboard.html"
    reports = [_make_report("v1", 0.5)]
    path = render_dashboard(reports, out)
    html = path.read_text(encoding="utf-8")
    # 类目标签应出现
    for cat in ["normal", "boundary", "missing", "induction", "refusal"]:
        assert cat in html, f"category '{cat}' must appear in dashboard"


def test_render_dashboard_no_external_assets_required(tmp_path: Path):
    """HTML 自包含(除 Chart.js CDN 外无其他外部依赖)。"""
    out = tmp_path / "dashboard.html"
    reports = [_make_report("v1", 0.5)]
    path = render_dashboard(reports, out)
    html = path.read_text(encoding="utf-8")
    # 只允许 CDN:chart.js/jsdelivr/cdnjs
    suspicious = ["http://", "https://"]
    # 提取外部 URL
    import re
    urls = re.findall(r'(https?://[^\s"\'<>]+)', html)
    # 全部应为已知 CDN
    allowed = ("cdn.jsdelivr.net", "cdnjs.cloudflare.com", "unpkg.com")
    for url in urls:
        assert any(a in url for a in allowed), (
            f"unexpected external URL: {url}; only allowed CDNs: {allowed}"
        )


def test_render_dashboard_handles_empty_reports(tmp_path: Path):
    """空报告列表应仍输出有效 HTML(占位)。"""
    out = tmp_path / "dashboard.html"
    path = render_dashboard([], out)
    assert path.exists()
    html = path.read_text(encoding="utf-8")
    assert "<html" in html.lower()
    # 应有"暂无数据"占位
    assert "暂无" in html or "no data" in html.lower() or "空" in html


def test_render_dashboard_escape_user_content(tmp_path: Path):
    """HTML 必须转义用户 query(防 XSS)。"""
    out = tmp_path / "dashboard.html"
    report = _make_report("v1", 0.5)
    # 在 by_category 加恶意数据应不破坏 HTML
    report["by_category"]["xss"] = {
        "total": 1,
        "pass": 0,
        "pass_rate": 0.0,
        "note": "<script>alert('xss')</script>",
    }
    path = render_dashboard([report], out)
    html = path.read_text(encoding="utf-8")
    # 直接 <script> 不应注入(可以出现在字符串字面量但不会执行)
    # 简单检查: 不应出现未转义的 <script> 标签
    import re
    inline_scripts = re.findall(r"<script[^>]*>(?!.*chart)", html, re.IGNORECASE | re.DOTALL)
    # 允许 1 个 chart.js + dashboard 自身的初始化 script
    assert len(inline_scripts) <= 2, "未转义的 inline <script> 过多,可能 XSS"