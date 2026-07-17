"""Plan-Execute：planner 产有序步骤 + executor 逐步执行。

spec §6.2.4。
- planner: LLM 把任务拆成 max_steps 个有序步骤，每步可选 tool_hint
- executor: 逐步跑 step_runner（注入便于测试/复用工具），失败即停并记 failed_step
"""
from __future__ import annotations

import json
import re

import structlog

logger = structlog.get_logger()
_FENCE_RE = re.compile(r"^```(?:json)?\s*|\s*```$", re.MULTILINE)

_PLAN_PROMPT = """把下面任务拆成有序执行步骤(最多 {max_steps} 步)。
每步给一句话描述,如需工具给 tool_hint(search_knowledge/diagnose_brand/generate_article/...)。
只输出 JSON 数组:[{{"step": "...", "tool_hint": "..."|null}}]

任务:{query}
"""


def _parse_steps(reply: str) -> list[dict]:
    """解析 LLM 回复为步骤列表。非法 / 非数组 / 缺少 step 字段 → 视为空(降级到 ReAct)。"""
    cleaned = _FENCE_RE.sub("", reply).strip()
    try:
        arr = json.loads(cleaned)
        if not isinstance(arr, list):
            return []
        out = []
        for s in arr:
            if isinstance(s, dict) and s.get("step"):
                out.append({"step": str(s["step"]), "tool_hint": s.get("tool_hint")})
        return out
    except (json.JSONDecodeError, TypeError):
        return []


async def plan(query: str, llm, max_steps: int = 6) -> list[dict]:
    """调 LLM 拆步骤，超 max_steps 截断。"""
    reply = await llm.simple_chat(_PLAN_PROMPT.format(query=query, max_steps=max_steps))
    return _parse_steps(reply)[:max_steps]


async def execute(steps: list[dict], step_runner, max_steps: int = 6) -> dict:
    """逐步执行。step_runner: async (step_dict, idx) -> result。

    某步抛异常 → 记 failed_step 并停止（上层可 replan / 降级）。
    """
    results: list = []
    for idx, step in enumerate(steps[:max_steps]):
        try:
            results.append(await step_runner(step, idx))
        except Exception as e:  # noqa: BLE001
            logger.warning("plan_step_failed", idx=idx, error=str(e))
            return {"results": results, "failed_step": idx}
    return {"results": results, "failed_step": None}
