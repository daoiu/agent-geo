"""ReflectionAgent：LLM-as-Judge 多维打分（完整 / 忠实 / 工具）+ 重试决策。

spec §6.2.3。
- 维度：completeness / faithfulness / tool_appropriateness，各 0-100
- 加权：0.4 / 0.4 / 0.2 → 综合 score
- 降级：无 LLM provider → available=False pass-through（不拦截）
- 失败：非法 JSON 或 LLM 异常 → score=0 available=True（让上层 retry 决策处理）
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass

import structlog

logger = structlog.get_logger()
_FENCE_RE = re.compile(r"^```(?:json)?\s*|\s*```$", re.MULTILINE)

_PROMPT = """你是答案质量评审。对下面【答案】按三维打分(各 0-100),并给一句改进建议。
维度:completeness(完整性) / faithfulness(忠实于工具结果、不编造) / tool_appropriateness(工具使用合理)。
只输出 JSON:{{"completeness": int, "faithfulness": int, "tool_appropriateness": int, "critique": "..."}}

【问题】{query}
【工具轨迹】{tool_trace}
【答案】{answer}
"""


@dataclass
class ReflectionResult:
    score: float
    completeness: float
    faithfulness: float
    tool_appropriateness: float
    critique: str
    available: bool


async def score_answer(query: str, answer: str, tool_trace: str, llm) -> ReflectionResult:
    if not getattr(llm, "available_providers", []):
        return ReflectionResult(100.0, 0, 0, 0, "", False)  # 不拦截
    try:
        reply = _FENCE_RE.sub(
            "",
            await llm.simple_chat(
                _PROMPT.format(query=query, tool_trace=tool_trace[:2000], answer=answer)
            ),
        ).strip()
        obj = json.loads(reply)
        c = float(obj["completeness"])
        f = float(obj["faithfulness"])
        t = float(obj["tool_appropriateness"])
        score = 0.4 * c + 0.4 * f + 0.2 * t
        return ReflectionResult(score, c, f, t, str(obj.get("critique", "")), True)
    except Exception as e:  # noqa: BLE001
        logger.warning("reflection_score_failed", error=str(e))
        return ReflectionResult(0.0, 0, 0, 0, "", True)


def should_retry(result: ReflectionResult, attempts_done: int, min_score: int, max_retries: int) -> bool:
    if not result.available:
        return False
    if result.score >= min_score:
        return False
    # max_retries 即"最多尝试次数"，已 attempts_done 次用尽则不再重试
    return attempts_done < max_retries


def pick_best(attempts: list[tuple[float, str]]) -> str:
    if not attempts:
        return ""
    return max(attempts, key=lambda x: x[0])[1]
