"""慢查询 dashboard(P1#34 / Task 35)。

输入:
- turn_durations: turn 端到端延迟列表(ms)
- llm_durations: LLM 调用延迟列表(ms)
- slow_queries: Top 慢查询列表 [{session_id, turn_ms, query, ...}]

输出:
- 静态 HTML(含 P50/P95/P99 + 慢查询列表 + 延迟分布图)
- 通过 Chart.js CDN 渲染
"""
from __future__ import annotations

import html as html_lib
from pathlib import Path
from typing import Iterable


CHARTJS_CDN = "https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"


def compute_percentiles(values: Iterable[float]) -> tuple[float, float, float]:
    """计算 P50 / P95 / P99。

    使用线性插值法(类似 numpy.percentile linear interpolation)。
    空输入返回 (0, 0, 0)。
    """
    sorted_vals = sorted(values)
    n = len(sorted_vals)
    if n == 0:
        return 0.0, 0.0, 0.0
    if n == 1:
        return float(sorted_vals[0]), float(sorted_vals[0]), float(sorted_vals[0])

    def _p(p: float) -> float:
        # 线性插值: idx = p/100 * (n-1)
        idx = (p / 100.0) * (n - 1)
        lo = int(idx)
        hi = min(lo + 1, n - 1)
        frac = idx - lo
        return sorted_vals[lo] * (1 - frac) + sorted_vals[hi] * frac

    return _p(50), _p(95), _p(99)


def _bucketize(values: list[float], buckets: list[tuple[float, float, str]]) -> dict[str, int]:
    """按区间分桶(用于分布图)。buckets 是 (low, high, label) 元组列表。"""
    counts = {label: 0 for _, _, label in buckets}
    for v in values:
        for low, high, label in buckets:
            if low <= v < high or (high == buckets[-1][1] and v == high):
                counts[label] += 1
                break
    return counts


def _safe(s) -> str:
    """HTML 转义(防 XSS)。"""
    if s is None:
        return ""
    return html_lib.escape(str(s))


def render_slow_query_dashboard(
    turn_durations: list[float],
    llm_durations: list[float],
    slow_queries: list[dict],
    out_path: Path,
    threshold_ms: float = 60_000.0,
) -> Path:
    """渲染慢查询 dashboard HTML。

    threshold_ms: 慢查询阈值(默认 60s,与告警阈值一致)。
    """
    out_path = Path(out_path)
    if not turn_durations and not llm_durations and not slow_queries:
        return _render_empty(out_path)

    turn_p50, turn_p95, turn_p99 = compute_percentiles(turn_durations)
    llm_p50, llm_p95, llm_p99 = compute_percentiles(llm_durations)

    # 慢查询数(超过阈值的)
    slow_count = sum(1 for v in turn_durations if v >= threshold_ms)

    # 延迟分桶
    buckets = [
        (0, 500, "<500ms"),
        (500, 1000, "0.5-1s"),
        (1000, 5000, "1-5s"),
        (5000, 30_000, "5-30s"),
        (30_000, 60_000, "30-60s"),
        (60_000, float("inf"), ">60s"),
    ]
    turn_dist = _bucketize(turn_durations, buckets)
    bucket_labels = [label for _, _, label in buckets]
    bucket_data = [turn_dist[label] for label in bucket_labels]

    # Top 慢查询表格
    sorted_slow = sorted(slow_queries, key=lambda q: -q.get("turn_ms", 0))[:20]
    rows_html = ""
    for q in sorted_slow:
        turn_ms = q.get("turn_ms", 0)
        color = "#ef4444" if turn_ms >= 60_000 else "#f59e0b" if turn_ms >= 30_000 else "#10b981"
        rows_html += f"""<tr>
  <td><code>{_safe(q.get('session_id', '-'))}</code></td>
  <td>{_safe(q.get('query', '')[:80])}</td>
  <td><span class="badge" style="background:{color}">{turn_ms:.0f} ms</span></td>
  <td>{_safe(q.get('timestamp', '-'))}</td>
</tr>"""

    bucket_labels_json = str(bucket_labels).replace("'", '"')
    bucket_data_json = str(bucket_data)

    body = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<title>GEO2 慢查询 Dashboard</title>
<script src="{CHARTJS_CDN}"></script>
<style>
  * {{ box-sizing: border-box; }}
  body {{ font-family: -apple-system, sans-serif; background: #fafafa;
         color: #1f2937; margin: 0; padding: 2rem; }}
  h1 {{ color: #0f172a; margin-bottom: 0.25rem; }}
  .subtitle {{ color: #6b7280; margin-bottom: 2rem; }}
  .cards {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: 1rem; margin-bottom: 2rem; }}
  .card {{ background: white; border-radius: 8px; padding: 1.25rem;
           box-shadow: 0 1px 3px rgba(0,0,0,0.08); }}
  .card.alert {{ border-left: 4px solid #ef4444; }}
  .card .label {{ color: #6b7280; font-size: 0.875rem; text-transform: uppercase; letter-spacing: 0.05em; }}
  .card .value {{ font-size: 1.75rem; font-weight: 600; margin-top: 0.5rem; }}
  .section {{ background: white; border-radius: 8px; padding: 1.5rem;
              box-shadow: 0 1px 3px rgba(0,0,0,0.08); margin-bottom: 2rem; }}
  .section h2 {{ margin-top: 0; color: #374151; }}
  table {{ width: 100%; border-collapse: collapse; }}
  th, td {{ padding: 0.75rem 1rem; text-align: left; border-bottom: 1px solid #f3f4f6; }}
  th {{ background: #f9fafb; color: #6b7280; font-weight: 600; font-size: 0.875rem; }}
  .badge {{ display: inline-block; padding: 0.2rem 0.6rem; border-radius: 4px;
            color: white; font-size: 0.875rem; font-weight: 600; }}
  .chart-box {{ max-height: 300px; }}
  .perf-grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 1rem; }}
  .perf-metric {{ background: #f9fafb; padding: 1rem; border-radius: 6px; text-align: center; }}
  .perf-metric .pct {{ font-size: 1.5rem; font-weight: 600; color: #0ea5e9; }}
  .perf-metric .name {{ color: #6b7280; font-size: 0.875rem; margin-top: 0.25rem; }}
</style>
</head>
<body>
<h1>GEO2 慢查询 Dashboard</h1>
<div class="subtitle">Generated: <span id="gen-time"></span></div>

<div class="cards">
  <div class="card">
    <div class="label">Turn 总数</div>
    <div class="value">{len(turn_durations)}</div>
  </div>
  <div class="card {'alert' if slow_count > 0 else ''}">
    <div class="label">慢查询数(≥{threshold_ms/1000:.0f}s)</div>
    <div class="value">{slow_count}</div>
  </div>
  <div class="card">
    <div class="label">慢查询阈值</div>
    <div class="value">{threshold_ms/1000:.0f}s</div>
  </div>
</div>

<div class="section">
  <h2>📊 延迟百分位</h2>
  <div class="perf-grid">
    <div>
      <h3 style="margin-top:0;color:#374151;">Turn 端到端</h3>
      <div class="perf-metric">
        <div class="pct">{turn_p50:.0f} ms</div>
        <div class="name">P50</div>
      </div>
      <div class="perf-metric" style="margin-top:0.5rem;">
        <div class="pct">{turn_p95:.0f} ms</div>
        <div class="name">P95</div>
      </div>
      <div class="perf-metric" style="margin-top:0.5rem;">
        <div class="pct">{turn_p99:.0f} ms</div>
        <div class="name">P99</div>
      </div>
    </div>
    <div>
      <h3 style="margin-top:0;color:#374151;">LLM 单次调用</h3>
      <div class="perf-metric">
        <div class="pct">{llm_p50:.0f} ms</div>
        <div class="name">P50</div>
      </div>
      <div class="perf-metric" style="margin-top:0.5rem;">
        <div class="pct">{llm_p95:.0f} ms</div>
        <div class="name">P95</div>
      </div>
      <div class="perf-metric" style="margin-top:0.5rem;">
        <div class="pct">{llm_p99:.0f} ms</div>
        <div class="name">P99</div>
      </div>
    </div>
  </div>
</div>

<div class="section">
  <h2>📈 Turn 延迟分布</h2>
  <div class="chart-box">
    <canvas id="distChart"></canvas>
  </div>
</div>

<div class="section">
  <h2>🐢 Top 慢查询</h2>
  <table>
    <thead><tr><th>Session</th><th>Query</th><th>Turn 耗时</th><th>时间</th></tr></thead>
    <tbody>{rows_html if rows_html else '<tr><td colspan="4" style="text-align:center;color:#9ca3af;">暂无慢查询</td></tr>'}</tbody>
  </table>
</div>

<script>
document.getElementById('gen-time').textContent = new Date().toLocaleString('zh-CN');
new Chart(document.getElementById('distChart'), {{
  type: 'bar',
  data: {{
    labels: {bucket_labels_json},
    datasets: [{{
      label: 'Turn 数',
      data: {bucket_data_json},
      backgroundColor: ['#10b981','#34d399','#fbbf24','#f59e0b','#ef4444','#7f1d1d'],
    }}]
  }},
  options: {{
    responsive: true,
    plugins: {{ legend: {{ display: false }} }},
    scales: {{ y: {{ beginAtZero: true, ticks: {{ stepSize: 1 }} }} }}
  }}
}});
</script>
</body>
</html>"""
    out_path.write_text(body, encoding="utf-8")
    return out_path


def _render_empty(out_path: Path) -> Path:
    body = """<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8">
<title>GEO2 慢查询 Dashboard - 暂无数据</title>
<style>
body { font-family: -apple-system, sans-serif; padding: 2rem; background: #fafafa; }
.empty { text-align: center; padding: 4rem; color: #999; font-size: 1.5rem; }
</style></head><body>
<h1>GEO2 慢查询 Dashboard</h1>
<div class="empty">暂无延迟数据</div>
</body></html>"""
    out_path.write_text(body, encoding="utf-8")
    return out_path


__all__ = [
    "compute_percentiles",
    "render_slow_query_dashboard",
]


if __name__ == "__main__":
    """CLI 入口:从结构化日志拉取数据 + 渲染 dashboard。"""
    import sys
    from pathlib import Path

    out = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("evals/slow_dashboard.html")
    # 占位:从 Prometheus / 日志文件聚合(后续接入)
    render_slow_query_dashboard(
        turn_durations=[],
        llm_durations=[],
        slow_queries=[],
        out_path=out,
    )
    print(f"[slow_query_dashboard] rendered: {out}")