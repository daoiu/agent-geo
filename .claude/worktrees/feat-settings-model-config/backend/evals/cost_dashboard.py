"""月度成本 dashboard(P2#49 / Task 39)。

输入:cost events 列表,每个含 timestamp/provider/model/cost_usd/prompt_tokens/completion_tokens
输出:静态 HTML dashboard,展示:
- 总成本 + token 用量
- 按月份聚合
- 按 provider / model 分布
- Top 成本事件
"""
from __future__ import annotations

import html as html_lib
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Iterable


CHARTJS_CDN = "https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"


def _parse_month(timestamp: str) -> str | None:
    """提取 YYYY-MM,失败返回 None。"""
    if not isinstance(timestamp, str) or not timestamp:
        return None
    # 兼容 ISO 8601 / 简化日期
    for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            dt = datetime.strptime(timestamp[: len(fmt) + 6], fmt)
            return f"{dt.year:04d}-{dt.month:02d}"
        except ValueError:
            continue
    # 最后尝试 fromisoformat
    try:
        dt = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
        return f"{dt.year:04d}-{dt.month:02d}"
    except (ValueError, AttributeError):
        return None


def aggregate_costs(events: Iterable[dict]) -> dict:
    """聚合 cost events:by_month / by_provider / by_model + totals。"""
    events = list(events)
    total_cost = 0.0
    total_prompt = 0
    total_completion = 0
    by_month: dict[str, dict] = defaultdict(lambda: {"cost_usd": 0.0, "events": 0, "tokens": 0})
    by_provider: dict[str, float] = defaultdict(float)
    by_model: dict[str, float] = defaultdict(float)
    by_month_provider: dict[str, dict[str, float]] = defaultdict(lambda: defaultdict(float))

    for ev in events:
        try:
            cost = float(ev.get("cost_usd", 0))
        except (ValueError, TypeError):
            continue
        month = _parse_month(ev.get("timestamp", ""))
        provider = str(ev.get("provider", "unknown"))
        model = str(ev.get("model", "unknown"))
        prompt = int(ev.get("prompt_tokens", 0) or 0)
        completion = int(ev.get("completion_tokens", 0) or 0)

        total_cost += cost
        total_prompt += prompt
        total_completion += completion
        by_provider[provider] += cost
        by_model[model] += cost
        if month:
            by_month[month]["cost_usd"] += cost
            by_month[month]["events"] += 1
            by_month[month]["tokens"] += prompt + completion
            by_month_provider[month][provider] += cost

    # 排序
    by_month_sorted = dict(sorted(by_month.items()))
    by_provider_sorted = dict(sorted(by_provider.items(), key=lambda kv: -kv[1]))
    by_model_sorted = dict(sorted(by_model.items(), key=lambda kv: -kv[1]))

    return {
        "total_cost_usd": total_cost,
        "total_prompt_tokens": total_prompt,
        "total_completion_tokens": total_completion,
        "by_month": by_month_sorted,
        "by_provider": by_provider_sorted,
        "by_model": by_model_sorted,
        "by_month_provider": {m: dict(v) for m, v in by_month_provider.items()},
    }


def _safe(s) -> str:
    if s is None:
        return ""
    return html_lib.escape(str(s))


def render_cost_dashboard(events: list[dict], out_path: Path) -> Path:
    """渲染月度成本 dashboard HTML。"""
    out_path = Path(out_path)
    agg = aggregate_costs(events)
    if not events:
        return _render_empty(out_path)

    # 按 provider 饼图
    provider_labels = list(agg["by_provider"].keys())
    provider_data = list(agg["by_provider"].values())

    # 按月份趋势
    months = list(agg["by_month"].keys())
    month_costs = [agg["by_month"][m]["cost_usd"] for m in months]

    # Top 模型
    top_models = list(agg["by_model"].items())[:10]

    # 月份明细表
    month_rows = ""
    for m, info in agg["by_month"].items():
        provider_breakdown = ", ".join(
            f"{_safe(p)} ${v:.3f}" for p, v in agg["by_month_provider"].get(m, {}).items()
        )
        month_rows += f"""<tr>
  <td>{_safe(m)}</td>
  <td>${info['cost_usd']:.3f}</td>
  <td>{info['events']}</td>
  <td>{info['tokens']:,}</td>
  <td><small>{provider_breakdown}</small></td>
</tr>"""

    # Top 模型表
    model_rows = ""
    for m, c in top_models:
        model_rows += f"<tr><td><code>{_safe(m)}</code></td><td>${c:.3f}</td></tr>"

    provider_labels_json = str(provider_labels).replace("'", '"')
    provider_data_json = str(provider_data)
    months_json = str(months).replace("'", '"')
    month_costs_json = str(month_costs)

    body = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<title>GEO2 月度成本 Dashboard</title>
<script src="{CHARTJS_CDN}"></script>
<style>
  * {{ box-sizing: border-box; }}
  body {{ font-family: -apple-system, sans-serif; background: #fafafa;
         color: #1f2937; margin: 0; padding: 2rem; }}
  h1 {{ color: #0f172a; margin-bottom: 0.25rem; }}
  .subtitle {{ color: #6b7280; margin-bottom: 2rem; }}
  .cards {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 1rem; margin-bottom: 2rem; }}
  .card {{ background: white; border-radius: 8px; padding: 1.25rem;
           box-shadow: 0 1px 3px rgba(0,0,0,0.08); }}
  .card.cost {{ border-left: 4px solid #ef4444; }}
  .card .label {{ color: #6b7280; font-size: 0.875rem; text-transform: uppercase; letter-spacing: 0.05em; }}
  .card .value {{ font-size: 2rem; font-weight: 600; margin-top: 0.5rem; }}
  .section {{ background: white; border-radius: 8px; padding: 1.5rem;
              box-shadow: 0 1px 3px rgba(0,0,0,0.08); margin-bottom: 2rem; }}
  .section h2 {{ margin-top: 0; color: #374151; }}
  table {{ width: 100%; border-collapse: collapse; }}
  th, td {{ padding: 0.75rem 1rem; text-align: left; border-bottom: 1px solid #f3f4f6; }}
  th {{ background: #f9fafb; color: #6b7280; font-weight: 600; font-size: 0.875rem; }}
  .charts {{ display: grid; grid-template-columns: 1fr 1fr; gap: 1.5rem; }}
  .chart-box {{ max-height: 320px; }}
</style>
</head>
<body>
<h1>GEO2 月度成本 Dashboard</h1>
<div class="subtitle">Generated: <span id="gen-time"></span></div>

<div class="cards">
  <div class="card cost">
    <div class="label">总成本</div>
    <div class="value">${agg['total_cost_usd']:.3f}</div>
  </div>
  <div class="card">
    <div class="label">Prompt Tokens</div>
    <div class="value">{agg['total_prompt_tokens']:,}</div>
  </div>
  <div class="card">
    <div class="label">Completion Tokens</div>
    <div class="value">{agg['total_completion_tokens']:,}</div>
  </div>
  <div class="card">
    <div class="label">事件数</div>
    <div class="value">{len(events)}</div>
  </div>
</div>

<div class="section">
  <h2>📈 月度趋势 & 按 Provider 分布</h2>
  <div class="charts">
    <div class="chart-box">
      <h3>月度成本趋势</h3>
      <canvas id="monthChart"></canvas>
    </div>
    <div class="chart-box">
      <h3>Provider 占比</h3>
      <canvas id="providerChart"></canvas>
    </div>
  </div>
</div>

<div class="section">
  <h2>📅 月度明细</h2>
  <table>
    <thead><tr><th>月份</th><th>成本</th><th>事件数</th><th>Tokens</th><th>Provider 分布</th></tr></thead>
    <tbody>{month_rows}</tbody>
  </table>
</div>

<div class="section">
  <h2>💰 Top 模型</h2>
  <table>
    <thead><tr><th>模型</th><th>成本</th></tr></thead>
    <tbody>{model_rows}</tbody>
  </table>
</div>

<script>
document.getElementById('gen-time').textContent = new Date().toLocaleString('zh-CN');

// 月度趋势
new Chart(document.getElementById('monthChart'), {{
  type: 'line',
  data: {{
    labels: {months_json},
    datasets: [{{
      label: '月成本 (USD)',
      data: {month_costs_json},
      borderColor: '#0ea5e9',
      backgroundColor: 'rgba(14, 165, 233, 0.1)',
      fill: true,
      tension: 0.3,
    }}]
  }},
  options: {{
    responsive: true,
    plugins: {{ legend: {{ display: false }} }},
    scales: {{ y: {{ beginAtZero: true }} }}
  }}
}});

// Provider 饼图
new Chart(document.getElementById('providerChart'), {{
  type: 'pie',
  data: {{
    labels: {provider_labels_json},
    datasets: [{{
      data: {provider_data_json},
      backgroundColor: ['#0ea5e9','#10b981','#f59e0b','#ef4444','#8b5cf6','#ec4899'],
    }}]
  }},
  options: {{ responsive: true }}
}});
</script>
</body>
</html>"""
    out_path.write_text(body, encoding="utf-8")
    return out_path


def _render_empty(out_path: Path) -> Path:
    body = """<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8">
<title>GEO2 成本 Dashboard - 暂无数据</title>
<style>
body { font-family: -apple-system, sans-serif; padding: 2rem; background: #fafafa; }
.empty { text-align: center; padding: 4rem; color: #999; font-size: 1.5rem; }
</style></head><body>
<h1>GEO2 月度成本 Dashboard</h1>
<div class="empty">暂无成本数据</div>
</body></html>"""
    out_path.write_text(body, encoding="utf-8")
    return out_path


__all__ = [
    "aggregate_costs",
    "render_cost_dashboard",
]


if __name__ == "__main__":
    import json
    import sys

    events_path = Path(sys.argv[1]) if len(sys.argv) > 1 else None
    out = Path(sys.argv[2]) if len(sys.argv) > 2 else Path("evals/cost_dashboard.html")

    if events_path and events_path.exists():
        events = json.loads(events_path.read_text(encoding="utf-8"))
    else:
        events = []

    path = render_cost_dashboard(events, out)
    print(f"[cost_dashboard] rendered: {path}")