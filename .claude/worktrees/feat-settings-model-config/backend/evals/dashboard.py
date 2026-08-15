"""评测可视化面板 — 静态 HTML + Chart.js (CDN)。

不引入 Python 图表库(避免 matplotlib 等重依赖),用 Chart.js 通过 CDN 渲染。

输出:
- 摘要卡片(总用例 / 通过率 / 平均分 / 平均延迟)
- 多版本 pass rate 趋势折线图
- 当前版本 by_category bar 图
- 详情表(各类别 pass rate)

使用:
    from evals.dashboard import render_dashboard
    render_dashboard([report1, report2], Path("dashboard.html"))
"""
from __future__ import annotations

import html
import json
from pathlib import Path
from typing import Iterable


CHARTJS_CDN = "https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"


def _format_pct(rate: float) -> str:
    return f"{rate * 100:.1f}%"


def _safe(s) -> str:
    """HTML 转义(防 XSS)。"""
    if s is None:
        return ""
    return html.escape(str(s))


def render_dashboard(reports: Iterable[dict], out_path: Path) -> Path:
    """渲染静态 HTML dashboard。

    reports: 多个报告 dict,每个含 label/total/pass/pass_rate/by_category
    out_path: HTML 输出路径
    """
    reports = list(reports)
    out_path = Path(out_path)

    if not reports:
        return _render_empty(out_path)

    latest = reports[-1]
    by_cat = latest.get("by_category", {})

    # 摘要数据
    summary = {
        "total": latest.get("total", 0),
        "pass": latest.get("pass", 0),
        "pass_rate": latest.get("pass_rate", 0.0),
        "avg_score": latest.get("avg_score", 0.0),
        "avg_latency_ms": latest.get("avg_latency_ms", 0.0),
        "label": latest.get("label", "latest"),
    }

    # 趋势数据(多版本)
    trend_labels = [r.get("label", f"v{i}") for i, r in enumerate(reports)]
    trend_pass_rates = [r.get("pass_rate", 0.0) for r in reports]

    # 类别数据(最新)
    cat_labels = list(by_cat.keys())
    cat_pass_rates = [by_cat[c].get("pass_rate", 0.0) for c in cat_labels]
    cat_totals = [by_cat[c].get("total", 0) for c in cat_labels]

    body = _render_html(
        summary=summary,
        trend_labels=trend_labels,
        trend_pass_rates=trend_pass_rates,
        cat_labels=cat_labels,
        cat_pass_rates=cat_pass_rates,
        cat_totals=cat_totals,
        reports=reports,
    )
    out_path.write_text(body, encoding="utf-8")
    return out_path


def _render_empty(out_path: Path) -> Path:
    body = """<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8">
<title>GEO2 评测面板 - 暂无数据</title>
<style>
body { font-family: -apple-system, sans-serif; padding: 2rem; background: #fafafa; }
.empty { text-align: center; padding: 4rem; color: #999; font-size: 1.5rem; }
</style></head><body>
<h1>GEO2 评测面板</h1>
<div class="empty">暂无评测数据</div>
</body></html>"""
    out_path.write_text(body, encoding="utf-8")
    return out_path


def _render_html(
    summary: dict,
    trend_labels: list[str],
    trend_pass_rates: list[float],
    cat_labels: list[str],
    cat_pass_rates: list[float],
    cat_totals: list[int],
    reports: list[dict],
) -> str:
    """渲染完整 HTML(用 Chart.js)。"""
    summary_json = json.dumps(summary, ensure_ascii=False)
    trend_labels_json = json.dumps(trend_labels, ensure_ascii=False)
    trend_data_json = json.dumps(trend_pass_rates, ensure_ascii=False)
    cat_labels_json = json.dumps(cat_labels, ensure_ascii=False)
    cat_pass_rates_json = json.dumps(cat_pass_rates, ensure_ascii=False)
    cat_totals_json = json.dumps(cat_totals, ensure_ascii=False)

    # 摘要卡片 HTML
    cards_html = f"""
<div class="cards">
  <div class="card">
    <div class="label">总用例</div>
    <div class="value">{summary['total']}</div>
  </div>
  <div class="card pass">
    <div class="label">Pass Rate</div>
    <div class="value">{_format_pct(summary['pass_rate'])}</div>
    <div class="sub">{summary['pass']} / {summary['total']}</div>
  </div>
  <div class="card">
    <div class="label">平均分</div>
    <div class="value">{summary['avg_score']:.3f}</div>
  </div>
  <div class="card">
    <div class="label">平均延迟</div>
    <div class="value">{summary['avg_latency_ms']:.0f} ms</div>
  </div>
</div>
"""

    # 类别表格
    rows_html = ""
    for cat, pr, total in zip(cat_labels, cat_pass_rates, cat_totals):
        color = "#10b981" if pr >= 0.7 else "#f59e0b" if pr >= 0.4 else "#ef4444"
        rows_html += f"""<tr>
  <td>{_safe(cat)}</td>
  <td>{total}</td>
  <td><span class="badge" style="background:{color}">{_format_pct(pr)}</span></td>
</tr>"""

    # 多版本表格
    versions_html = ""
    for r in reports:
        versions_html += f"""<tr>
  <td>{_safe(r.get('label', '-'))}</td>
  <td>{r.get('total', 0)}</td>
  <td>{_format_pct(r.get('pass_rate', 0.0))}</td>
  <td>{r.get('avg_score', 0.0):.3f}</td>
  <td>{r.get('avg_latency_ms', 0.0):.0f} ms</td>
</tr>"""

    html_doc = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<title>GEO2 评测面板</title>
<script src="{CHARTJS_CDN}"></script>
<style>
  * {{ box-sizing: border-box; }}
  body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
         background: #fafafa; color: #1f2937; margin: 0; padding: 2rem; }}
  h1 {{ color: #0f172a; margin-bottom: 0.25rem; }}
  .subtitle {{ color: #6b7280; margin-bottom: 2rem; }}
  .cards {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 1rem; margin-bottom: 2rem; }}
  .card {{ background: white; border-radius: 8px; padding: 1.25rem;
           box-shadow: 0 1px 3px rgba(0,0,0,0.08); }}
  .card.pass {{ border-left: 4px solid #10b981; }}
  .card .label {{ color: #6b7280; font-size: 0.875rem; text-transform: uppercase; letter-spacing: 0.05em; }}
  .card .value {{ font-size: 2rem; font-weight: 600; margin-top: 0.5rem; }}
  .card .sub {{ color: #9ca3af; font-size: 0.875rem; margin-top: 0.25rem; }}
  .charts {{ display: grid; grid-template-columns: 1fr 1fr; gap: 1.5rem; margin-bottom: 2rem; }}
  .chart-box {{ background: white; border-radius: 8px; padding: 1.5rem;
                box-shadow: 0 1px 3px rgba(0,0,0,0.08); }}
  .chart-box h3 {{ margin-top: 0; color: #374151; }}
  .chart-box canvas {{ max-height: 300px; }}
  table {{ width: 100%; border-collapse: collapse; background: white;
           border-radius: 8px; overflow: hidden; box-shadow: 0 1px 3px rgba(0,0,0,0.08); }}
  th, td {{ padding: 0.75rem 1rem; text-align: left; border-bottom: 1px solid #f3f4f6; }}
  th {{ background: #f9fafb; color: #6b7280; font-weight: 600; font-size: 0.875rem; }}
  .badge {{ display: inline-block; padding: 0.2rem 0.6rem; border-radius: 4px;
            color: white; font-size: 0.875rem; font-weight: 600; }}
  h2 {{ color: #0f172a; margin: 2rem 0 1rem; }}
</style>
</head>
<body>
<h1>GEO2 评测面板</h1>
<div class="subtitle">Latest: {_safe(summary['label'])} • Generated: <span id="gen-time"></span></div>

{cards_html}

<h2>📈 趋势 & 分布</h2>
<div class="charts">
  <div class="chart-box">
    <h3>Pass Rate 趋势(多版本)</h3>
    <canvas id="trendChart"></canvas>
  </div>
  <div class="chart-box">
    <h3>各类别 Pass Rate</h3>
    <canvas id="categoryChart"></canvas>
  </div>
</div>

<h2>📊 类别详情</h2>
<table>
  <thead><tr><th>类目</th><th>用例数</th><th>Pass Rate</th></tr></thead>
  <tbody>{rows_html}</tbody>
</table>

<h2>🕐 版本历史</h2>
<table>
  <thead><tr><th>版本</th><th>总用例</th><th>Pass Rate</th><th>平均分</th><th>平均延迟</th></tr></thead>
  <tbody>{versions_html}</tbody>
</table>

<script>
document.getElementById('gen-time').textContent = new Date().toLocaleString('zh-CN');

// 趋势图
new Chart(document.getElementById('trendChart'), {{
  type: 'line',
  data: {{
    labels: {trend_labels_json},
    datasets: [{{
      label: 'Pass Rate',
      data: {trend_data_json},
      borderColor: '#0ea5e9',
      backgroundColor: 'rgba(14, 165, 233, 0.1)',
      tension: 0.3,
      fill: true,
      pointRadius: 5,
    }}]
  }},
  options: {{
    responsive: true,
    plugins: {{ legend: {{ display: false }} }},
    scales: {{
      y: {{ beginAtZero: true, max: 1.0,
            ticks: {{ callback: v => (v*100).toFixed(0)+'%' }} }}
    }}
  }}
}});

// 类别柱状图
new Chart(document.getElementById('categoryChart'), {{
  type: 'bar',
  data: {{
    labels: {cat_labels_json},
    datasets: [{{
      label: 'Pass Rate',
      data: {cat_pass_rates_json},
      backgroundColor: {cat_pass_rates_json}.map(v =>
        v >= 0.7 ? '#10b981' : v >= 0.4 ? '#f59e0b' : '#ef4444'),
    }}]
  }},
  options: {{
    responsive: true,
    plugins: {{ legend: {{ display: false }} }},
    scales: {{
      y: {{ beginAtZero: true, max: 1.0,
            ticks: {{ callback: v => (v*100).toFixed(0)+'%' }} }}
    }}
  }}
}});
</script>
</body>
</html>
"""
    return html_doc


__all__ = ["render_dashboard"]


if __name__ == "__main__":
    """CLI: 跑评测 → 渲染 dashboard。"""
    import asyncio
    import sys

    from .runner import run_all

    out = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("evals/dashboard.html")

    print("[dashboard] 跑评测...")
    report = asyncio.run(run_all()).to_dict(include_details=False)
    report["label"] = "latest"
    print(f"[dashboard] 跑完: pass_rate={report['pass_rate']}")

    print(f"[dashboard] 渲染到 {out}...")
    path = render_dashboard([report], out)
    print(f"[dashboard] 完成: {path}")