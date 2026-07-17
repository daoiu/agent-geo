"""模式路由：入口复杂度选模式 + 运行时升降级判定。

spec §6.2.2 / §6.2.4。
- 入口：query 长度 + hint → complex 走 Plan-Execute，其余走 ReAct
- 运行时：ReAct 触顶或连续工具失败 ≥2 → 升级 Plan-Execute（单向，防震荡）
- planner 失败 / 无有效步骤 → 降级回 ReAct
"""
from __future__ import annotations

from app.core.adaptive_model import classify_complexity

MODE_REACT = "react"
MODE_PLAN = "plan_execute"


def choose_mode(query: str, hint: str | None = None) -> str:
    # 入口未知实际 tool 数，tool_count=0 靠 query 长度 + hint 分类
    complexity = classify_complexity(query, tool_count=0, hint=hint)
    return MODE_PLAN if complexity == "complex" else MODE_REACT


def should_escalate(state: dict) -> bool:
    """ReAct 升 Plan-Execute 判定。单向：已升级不再降回。"""
    if state.get("escalated"):
        return False
    if state.get("outcome") == "max_iterations_reached":
        return True
    return state.get("consecutive_tool_failures", 0) >= 2


def should_downgrade(steps: list | None) -> bool:
    """planner 产出无可用步骤 → 降级回 ReAct。"""
    return not steps
