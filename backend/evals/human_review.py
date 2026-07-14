"""人评抽样 + 导出。

为评测结果生成可人工 review 的样本集:
- `sample_for_review(report, n, seed)` — 优先失败 + 边界,带 seed 可复现
- `stratified_sample(report, n, seed)` — 分层抽样覆盖各类别
- `export_csv(samples, out_path)` — 机器可读 CSV(便于人工录入评分)
- `export_markdown(samples, out_path)` — 人可读 Markdown(便于直接在 PR/Issue 评审)
"""
from __future__ import annotations

import csv
import hashlib
import random
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable


@dataclass
class HumanSample:
    id: str
    category: str
    query: str
    response: str
    expected_keywords: list[str]
    expected_tool: str | None
    judge_pass: bool
    judge_score: float
    judge_reason: str = ""
    latency_ms: float = 0.0
    human_score: float | None = None
    human_note: str = ""

    def to_dict(self) -> dict:
        d = asdict(self)
        # 列表在 CSV 里要 stringify
        d["expected_keywords"] = "|".join(self.expected_keywords)
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "HumanSample":
        d = dict(d)
        kw = d.get("expected_keywords", "")
        if isinstance(kw, str):
            d["expected_keywords"] = [k for k in kw.split("|") if k]
        return cls(**d)


def _make_id(category: str, query: str) -> str:
    """基于 category+query 派生稳定 id(便于跨次跑对比)。"""
    h = hashlib.sha1(f"{category}:{query}".encode("utf-8")).hexdigest()[:8]
    return f"{category[:3]}-{h}"


def _detail_to_sample(detail: dict) -> HumanSample:
    """把 runner 输出的 detail dict 转 HumanSample。

    兼容两种 detail 格式:
    - runner 输出: {category, query, result: {pass, score, ...}, latency_ms}
    - 已有 case 字段: {category, query, expected_keywords, expected_tool, ...}
    """
    query = detail.get("query", "")
    category = detail.get("category", "unknown")
    result = detail.get("result", {})
    # runner 输出里 expected_keywords 在 case 上,不在 detail 里;
    # 测试 fixture 可能把 expected_keywords 也放进 detail。
    # 这里安全获取: detail 里有就用,否则空 list。
    return HumanSample(
        id=_make_id(category, query),
        category=category,
        query=query,
        response=detail.get("response", ""),
        expected_keywords=detail.get("expected_keywords", []) or [],
        expected_tool=detail.get("expected_tool"),
        judge_pass=bool(result.get("pass", False)),
        judge_score=float(result.get("score", 0.0)),
        judge_reason=result.get("reason", ""),
        latency_ms=float(detail.get("latency_ms", 0.0)),
    )


def _priority_key(detail: dict) -> tuple[int, float]:
    """排序优先级: 失败 + 边界 + 低分靠前。

    返回 (neg_cat_weight, score): 排序后 cat_weight 高 + score 低者靠前。
    """
    result = detail.get("result", {})
    is_fail = not result.get("pass", False)
    is_boundary = detail.get("category") == "boundary"
    is_missing = detail.get("category") == "missing"
    score = float(result.get("score", 1.0))
    cat_weight = (1 if is_fail else 0) + (1 if is_boundary else 0) + (1 if is_missing else 0)
    return (-cat_weight, score)  # cat_weight 高者 -cat 小 -> 排前; score 小者排前


def sample_for_review(report: dict, n: int = 10, seed: int | None = None) -> list[HumanSample]:
    """随机抽 N 条样本,优先失败 + 边界 + 低分。seed 用于可复现。

    报告: runner.run_all().to_dict() 返回的字典(含 details 列表)。
    策略: 70% 来自"高优先级桶"(前 50% 详情),30% 来自剩余(增加多样性)。
    """
    details: list[dict] = list(report.get("details", []))
    if not details:
        return []

    sorted_details = sorted(details, key=_priority_key)
    n = min(n, len(sorted_details))

    rng = random.Random(seed)
    high_priority_count = max(1, len(sorted_details) // 2)
    high_priority = sorted_details[:high_priority_count]
    low_priority = sorted_details[high_priority_count:]

    n_high = min(int(n * 0.7), len(high_priority))
    n_low = n - n_high

    selected: list[dict] = []
    if high_priority:
        selected.extend(rng.sample(high_priority, n_high))
    if low_priority and n_low > 0:
        n_low = min(n_low, len(low_priority))
        selected.extend(rng.sample(low_priority, n_low))

    # 如果 high 池不足,补足
    if len(selected) < n:
        remaining = [d for d in sorted_details if d not in selected]
        need = n - len(selected)
        if remaining:
            selected.extend(rng.sample(remaining, min(need, len(remaining))))

    return [_detail_to_sample(d) for d in selected]


def stratified_sample(report: dict, n: int = 10, seed: int | None = None) -> list[HumanSample]:
    """分层抽样:按类别比例抽,确保覆盖各类别。"""
    details: list[dict] = list(report.get("details", []))
    if not details:
        return []

    by_cat: dict[str, list[dict]] = {}
    for d in details:
        by_cat.setdefault(d.get("category", "unknown"), []).append(d)

    rng = random.Random(seed)
    total = len(details)
    samples: list[HumanSample] = []
    allocated = 0

    categories = sorted(by_cat.items(), key=lambda kv: -len(kv[1]))
    for i, (cat, cat_details) in enumerate(categories):
        if i == len(categories) - 1:
            count = n - allocated
        else:
            count = max(1, round(n * len(cat_details) / total))
        count = min(count, len(cat_details))
        allocated += count
        cat_sorted = sorted(cat_details, key=_priority_key)
        top_half = cat_sorted[: max(1, len(cat_sorted) // 2 + 1)]
        chosen = rng.sample(top_half, min(count, len(top_half)))
        samples.extend(_detail_to_sample(d) for d in chosen)

    return samples


def export_csv(samples: Iterable[HumanSample], out_path: Path) -> Path:
    """导出 CSV:字段含 id/category/query/response/expected_keywords/judge_*/human_*/latency_ms。"""
    out_path = Path(out_path)
    samples = list(samples)
    fields = [
        "id", "category", "query", "response", "expected_keywords",
        "expected_tool", "judge_pass", "judge_score", "judge_reason",
        "latency_ms", "human_score", "human_note",
    ]
    with out_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for s in samples:
            row = s.to_dict()
            for k in fields:
                row.setdefault(k, "")
            writer.writerow(row)
    return out_path


def export_markdown(samples: Iterable[HumanSample], out_path: Path) -> Path:
    """导出 Markdown:按类别分组,易读表格。"""
    out_path = Path(out_path)
    samples = list(samples)
    by_cat: dict[str, list[HumanSample]] = {}
    for s in samples:
        by_cat.setdefault(s.category, []).append(s)

    lines: list[str] = []
    lines.append("# 人评抽样报告\n")
    lines.append(f"> 总样本数: {len(samples)} | 类别数: {len(by_cat)}\n")
    fail_count = sum(1 for s in samples if not s.judge_pass)
    lines.append(f"> judge_pass=False: {fail_count} / {len(samples)}\n\n")

    lines.append("## 摘要表\n")
    lines.append("| ID | 类目 | Judge | Score | Query |")
    lines.append("| --- | --- | --- | --- | --- |")
    for s in samples:
        mark = "✅" if s.judge_pass else "❌"
        query_short = s.query[:60] + ("…" if len(s.query) > 60 else "")
        lines.append(f"| `{s.id}` | {s.category} | {mark} | {s.judge_score:.2f} | {query_short} |")
    lines.append("")

    lines.append("## 详细样本(按类目)\n")
    for cat in sorted(by_cat.keys()):
        lines.append(f"### {cat}\n")
        for s in by_cat[cat]:
            mark = "✅" if s.judge_pass else "❌"
            lines.append(f"#### `{s.id}` {mark} score={s.judge_score:.2f}\n")
            lines.append(f"- **Query**: {s.query}\n")
            lines.append(f"- **Expected Keywords**: {', '.join(s.expected_keywords) or '(无)'}\n")
            if s.expected_tool:
                lines.append(f"- **Expected Tool**: `{s.expected_tool}`\n")
            lines.append(f"- **Judge Reason**: {s.judge_reason}\n")
            lines.append(f"- **Response**:\n\n```\n{s.response[:800]}\n```\n")
            lines.append(f"- **Human Review**: score=`__` note=`__`\n\n")

    out_path.write_text("\n".join(lines), encoding="utf-8")
    return out_path


__all__ = [
    "HumanSample",
    "sample_for_review",
    "stratified_sample",
    "export_csv",
    "export_markdown",
]


if __name__ == "__main__":
    """CLI: 跑评测 → 抽样 → 导出。"""
    import asyncio
    import json
    import sys

    from .runner import run_all

    n = int(sys.argv[1]) if len(sys.argv) > 1 else 10
    seed = int(sys.argv[2]) if len(sys.argv) > 2 else 42
    out_dir = Path(sys.argv[3]) if len(sys.argv) > 3 else Path("evals/human_review_out")
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"[human_review] 跑评测...")
    report = asyncio.run(run_all()).to_dict(include_details=True)
    print(f"[human_review] 跑完: {report['total']} 条, pass_rate={report['pass_rate']}")

    print(f"[human_review] 抽样 n={n}, seed={seed}...")
    samples = sample_for_review(report, n=n, seed=seed)
    print(f"[human_review] 抽到 {len(samples)} 条")

    csv_path = export_csv(samples, out_dir / "review.csv")
    md_path = export_markdown(samples, out_dir / "review.md")
    print(f"[human_review] CSV: {csv_path}")
    print(f"[human_review] MD:  {md_path}")
    print(json.dumps({"n": len(samples), "csv": str(csv_path), "md": str(md_path)},
                     ensure_ascii=False, indent=2))