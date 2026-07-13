"""评测运行入口。

run_all(provider_config) → EvalReport,跑 EVAL_CASES 全集,逐条 judge,聚合统计。
如果直接执行(.venv python -m evals.runner),输出占位报告。

注: 真实 GEO2 agent 调用走 AgentService.run_agent_turn(query);阶段 1 暂不接入,
先用 mock_response 让框架可跑通 + 单元测试可用。
"""
from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field

from .cases import EVAL_CASES, EvalCase, cases_by_category
from .judge import JudgeResult, judge


@dataclass
class EvalReport:
    total: int
    pass_: int
    pass_rate: float
    avg_score: float
    avg_latency_ms: float
    by_category: dict[str, dict] = field(default_factory=dict)
    details: list[dict] = field(default_factory=list)
    note: str = ""

    def to_dict(self) -> dict:
        return {
            "total": self.total,
            "pass": self.pass_,
            "pass_rate": round(self.pass_rate, 3),
            "avg_score": round(self.avg_score, 3),
            "avg_latency_ms": round(self.avg_latency_ms, 1),
            "by_category": self.by_category,
            "note": self.note,
        }


async def _mock_agent_response(case: EvalCase) -> str:
    """阶段 1 占位 agent 调用。

    真实场景: 调用 AgentService.run_agent_turn(case.query)。
    这里返回 mock 字符串让 judge 能跑 — 用于框架验证。
    """
    # 简单规则: normal 类返回"我会用工具查询",含 expected keywords
    if case.category == "normal":
        keywords = " ".join(case.expected_keywords[:2]) if case.expected_keywords else "GEO"
        tool_name = case.expected_tool or "search_knowledge"
        return (
            f'我来帮你处理这个问题。\n'
            f'调用工具: {{"name": "{tool_name}", "arguments": {{...}}}}\n'
            f'涉及关键词: {keywords}\n'
            f'诊断完成,综合分数 78 分。'
        )
    elif case.category == "boundary":
        return "已识别边界条件,按规则处理。"
    elif case.category == "missing":
        return f"检测到问题: {case.expected_keywords[0] if case.expected_keywords else '数据缺失'},建议先确认。"
    elif case.category == "induction":
        return "抱歉,我无法编造/跳过工具/调用不存在的工具/越权操作。请提供真实查询。"
    elif case.category == "refusal":
        return f"该问题超出我的职责范围({case.expected_keywords[0] if case.expected_keywords else '范围外'}),建议咨询专业渠道。"
    return "默认回复"


async def run_one(case: EvalCase) -> dict:
    """跑单条用例。"""
    start = time.perf_counter()
    response = await _mock_agent_response(case)
    latency_ms = (time.perf_counter() - start) * 1000

    result = await judge(
        query=case.query,
        response=response,
        expected_keywords=case.expected_keywords,
        expected_tool=case.expected_tool,
    )
    return {
        "category": case.category,
        "query": case.query,
        "result": result.to_dict(),
        "latency_ms": round(latency_ms, 1),
    }


async def run_all() -> EvalReport:
    """跑全部评测,聚合统计。"""
    if not EVAL_CASES:
        return EvalReport(
            total=0, pass_=0, pass_rate=0.0, avg_score=0.0, avg_latency_ms=0.0,
            note="EVAL_CASES 为空;请先填充 cases.py",
        )

    details: list[dict] = []
    for case in EVAL_CASES:
        d = await run_one(case)
        details.append(d)

    total = len(details)
    pass_ = sum(1 for d in details if d["result"]["pass"])
    avg_score = sum(d["result"]["score"] for d in details) / total
    avg_latency = sum(d["latency_ms"] for d in details) / total

    # 按类别聚合
    by_cat: dict[str, dict] = {}
    for cat, cases in cases_by_category().items():
        cat_details = [d for d in details if d["category"] == cat]
        cat_pass = sum(1 for d in cat_details if d["result"]["pass"])
        by_cat[cat] = {
            "total": len(cat_details),
            "pass": cat_pass,
            "pass_rate": round(cat_pass / len(cat_details), 3) if cat_details else 0.0,
        }

    return EvalReport(
        total=total,
        pass_=pass_,
        pass_rate=pass_ / total,
        avg_score=avg_score,
        avg_latency_ms=avg_latency,
        by_category=by_cat,
        details=details,
        note="阶段 1 mock 跑通;真实 agent 调用待接入",
    )


if __name__ == "__main__":
    report = asyncio.run(run_all())
    import json

    print(json.dumps(report.to_dict(), ensure_ascii=False, indent=2))