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

    def to_dict(self, include_details: bool = False) -> dict:
        """序列化。include_details=True 时包含每条详情(用于人评抽样)。"""
        d = {
            "total": self.total,
            "pass": self.pass_,
            "pass_rate": round(self.pass_rate, 3),
            "avg_score": round(self.avg_score, 3),
            "avg_latency_ms": round(self.avg_latency_ms, 1),
            "by_category": self.by_category,
            "note": self.note,
        }
        if include_details:
            d["details"] = self.details
        return d


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


# ===========================================================================
# v0.8 — Compare 双跑 (spec §10.1 / Task 13)
# 注:这部分的函数定义移到 __main__ 之前,确保 main block 调用时函数已定义
# ===========================================================================
import json
from pathlib import Path
from typing import Any, AsyncIterator


async def _collect_sse(run_fn, session_id: str, message: str) -> list[dict]:
    """收集 AsyncIterator[bytes] 的 SSE chunk 并解析为 list[dict]。"""
    chunks = []
    async for sse in run_fn(session_id=session_id, message=message):
        try:
            chunks.append(json.loads(sse))
        except json.JSONDecodeError:
            pass
    return chunks


def _rouge_l(a: str, b: str) -> float:
    """简化 ROUGE-L:最长公共子序列长度 / max(len(a), len(b))。"""
    if not a or not b:
        return 0.0 if a != b else 1.0
    la, lb = a.split(), b.split()
    m, n = len(la), len(lb)
    dp = [[0] * (n + 1) for _ in range(m + 1)]
    for i in range(m):
        for j in range(n):
            dp[i + 1][j + 1] = (
                dp[i][j] + 1 if la[i] == lb[j] else max(dp[i + 1][j], dp[i][j + 1])
            )
    return dp[m][n] / max(m, n)


async def compare_evals(cases: list[dict], output_dir: Path) -> dict[str, Any]:
    """同一 input 跑 react_loop 与 langgraph,产出 diff 报告(spec §10.1)。

    Returns:
        dict 含 overall_match / tool_call_match / handoff_match / sse_event_count_equal

    注:T9 parity — 用临时 SQLite + init_db + 预建 session + monkeypatch
    全局 session factory + mock LLM(固定 tool_calls 返回),
    避免真实 LLM 非确定性导致 token-level 差异让 parity 永远不达标。
    """
    import os
    import tempfile
    from unittest.mock import AsyncMock, patch

    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    from app.core.db import init_db
    from app.domain.agent.dispatch import _run_langgraph_turn
    from app.models.orm import Base
    from app.repositories.agent_repo import AgentRepository

    # T10 后 react_loop 已删,只跑 LangGraph 单路径。
    # CR-3:compare_evals 改为 LangGraph 自对比(mock LLM 注入一致性)而非 react_loop vs LangGraph。

    # 临时 DB(避免污染 production)
    fd, db_path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    db_url = f"sqlite+aiosqlite:///{db_path}"
    engine = create_async_engine(db_url)

    # init schema(导入所有 ORM model)
    from app.models import orm as _orm_v01  # noqa: F401
    try:
        from app.models import orm_v04 as _orm_v04  # noqa: F401
    except ImportError:
        pass

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    factory = async_sessionmaker(engine, expire_on_commit=False)

    # Monkeypatch 全局 _session_factory(react_loop / langgraph 内部都用 get_session_factory)
    import app.core.db as core_db
    old_session_factory = core_db._session_factory
    core_db._session_factory = factory

    # Mock LLMClient(react_loop 和 react_graph 共用) — 固定返回 text-only,
    # 避免真实 LLM 非确定性 + 避免外网调用
    class _StubLLM:
        last_call_duration_ms = 0

        def __init__(self, settings=None, *args, **kwargs):
            pass

        def primary_provider_name(self):
            return "stub"

        async def chat_with_tools(self, messages, tools):
            return {"content": "stub response", "tool_calls": None, "usage": None}

    # T10 后 react_loop 已删,只 patch LangGraph 路径。
    # 关键:patch `app.domain.llm_client.LLMClient`(真正源头)而非 react_loop 模块
    import app.domain.agent.react_graph as rg_mod
    import app.domain.llm_client as llm_client_mod

    rg_patcher = patch.object(rg_mod, "LLMClient", _StubLLM)
    src_patcher = patch.object(llm_client_mod, "LLMClient", _StubLLM)
    rg_patcher.start()
    src_patcher.start()

    # Mock ToolExecutor(避免真实工具外网调用)
    class _StubTE:
        def __init__(self, session_id):
            self.session_id = session_id

        async def execute(self, name, args):
            return {"echo": args or {}, "name": name}

    # patch react_loop.ToolExecutor 和 react_graph._tool_node 内部 import 路径
    import app.domain.agent.tool_executor as te_mod
    te_patcher = patch.object(te_mod, "ToolExecutor", _StubTE)
    te_patcher.start()

    overall_matches: list[float] = []
    tool_matches: list[float] = []
    handoff_matches: list[float] = []
    sse_counts: list[bool] = []

    # 预建 session
    for c in cases:
        async with factory() as session:
            await AgentRepository(session).create_session(title=f"compare-{c['session_id']}")

    try:
        for c in cases:
            # T10 后 react_loop 已删,改为 LangGraph 单路径自检:
            # 同 case 跑两次,验证两次输出一致(LLM 已 mock → 确定性)
            chunks_a = await _collect_sse(_run_langgraph_turn, c["session_id"], c["message"])
            chunks_b = await _collect_sse(_run_langgraph_turn, c["session_id"], c["message"])

            # text 相似度(两次跑应一致,LLM mock 后确定性 1.0)
            text_a = "".join(
                x.get("content", "") for x in chunks_a
                if x.get("event") == "assistant_message"
            )
            text_b = "".join(
                x.get("content", "") for x in chunks_b
                if x.get("event") == "assistant_message"
            )
            overall_matches.append(_rouge_l(text_a, text_b))

            # tool_call 一致
            tools_a = {x.get("tool_name") for x in chunks_a if x.get("event") == "tool_call_start"}
            tools_b = {x.get("tool_name") for x in chunks_b if x.get("event") == "tool_call_start"}
            tool_matches.append(1.0 if tools_a == tools_b else 0.0)

            # handoff event 一致
            handoff_a = sum(1 for x in chunks_a if x.get("event") == "human_confirmation_required")
            handoff_b = sum(1 for x in chunks_b if x.get("event") == "human_confirmation_required")
            handoff_matches.append(1.0 if handoff_a == handoff_b else 0.0)

            sse_counts.append(len(chunks_a) == len(chunks_b))
    finally:
        rg_patcher.stop()
        src_patcher.stop()
        te_patcher.stop()
        # 恢复全局 _session_factory(否则污染同进程后续测试 / CLI 后续命令)
        core_db._session_factory = old_session_factory

    report = {
        "overall_match": sum(overall_matches) / len(overall_matches) if overall_matches else 1.0,
        "tool_call_match": sum(tool_matches) / len(tool_matches),
        "handoff_match": sum(handoff_matches) / len(handoff_matches),
        "sse_event_count_equal": all(sse_counts),
    }

    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "diff_report.md").write_text(
        f"""# Compare Report (CR-3: LangGraph 单路径自检,T10 后 react_loop 已删)
overall_match: {report['overall_match']:.3f}
tool_call_match: {report['tool_call_match']}
handoff_match: {report['handoff_match']}
sse_event_count_equal: {report['sse_event_count_equal']}

注:T10 删 react_loop 后,此 CLI 改为 LangGraph 单路径自检(同 case 跑两次,
LLM mock 后确定性 → 期望全部为 1.0/true)。
""",
        encoding="utf-8",
    )

    # 清理临时 DB
    await engine.dispose()
    try:
        os.remove(db_path)
    except OSError:
        pass

    return report


if __name__ == "__main__":
    import sys

    # CLI: --compare LangGraph 单路径自检(T10 后 react_loop 已删)
    if "--compare" in sys.argv:
        from pathlib import Path

        from .cases import EVAL_CASES

        out = Path("reports/eval/diff")
        cases = [
            # EvalCase 无 id 字段,用 query 派生稳定 session_id(hash 截断)
            {"session_id": f"compare-{hash(c.query) & 0xffffff:06x}", "message": c.query}
            for c in EVAL_CASES[:10]
        ]
        report = asyncio.run(compare_evals(cases, output_dir=out))
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        report = asyncio.run(run_all())
        print(json.dumps(report.to_dict(), ensure_ascii=False, indent=2))


__all__ = ["EvalReport", "run_all", "compare_evals"]  # noqa: F822