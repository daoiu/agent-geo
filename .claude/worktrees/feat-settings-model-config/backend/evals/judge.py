"""LLM-as-judge + 启发式评分。

两层评分:
1. keyword_score: expected_keywords 在 response 中出现的比例(0-1)
2. tool_score: 如果 response 中包含 tool_call,期望工具是否匹配(0/1)
3. llm_score (可选): 若 OPENAI_API_KEY 等价 secret 存在,调用 LLM 评 0-1

最终 score = 0.5 * keyword_score + 0.3 * tool_score + 0.2 * llm_score
(若无 LLM 评分能力,llm_score=0.5 中性值,等价于 keyword+tool 加权 0.8/0.5)

pass 判定: score >= 0.5
"""
from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass


@dataclass
class JudgeResult:
    pass_: bool
    score: float
    keyword_score: float
    tool_score: float
    llm_score: float
    reason: str

    def to_dict(self) -> dict:
        return {
            "pass": self.pass_,
            "score": round(self.score, 3),
            "keyword_score": round(self.keyword_score, 3),
            "tool_score": round(self.tool_score, 3),
            "llm_score": round(self.llm_score, 3),
            "reason": self.reason,
        }


def _keyword_score(response: str, expected: list[str]) -> float:
    """期望关键词在 response 中出现的比例。"""
    if not expected:
        return 1.0
    resp_lower = response.lower()
    hit = sum(1 for kw in expected if kw.lower() in resp_lower)
    return hit / len(expected)


def _tool_score(response: str, expected_tool: str | None) -> float:
    """如果 response 中含 tool_call,验证是否匹配期望工具。

    启发式: 抓 response 中的 `"name": "xxx"` JSON 字段。
    若 expected_tool=None(不强制),给 0.5 中性分。
    """
    if expected_tool is None:
        return 0.5

    # 抓取 tool_call 中的 name 字段
    m = re.search(r'"name"\s*:\s*"([^"]+)"', response)
    if not m:
        # 没找到 tool_call:若 query 真的需要工具,给低分;否则给 0.5
        return 0.3
    actual_tool = m.group(1)
    return 1.0 if actual_tool == expected_tool else 0.0


async def _llm_score(query: str, response: str, expected: list[str]) -> float:
    """LLM-as-judge: 调用 LLM 评 0-1。失败时返回 0.5 中性值。

    复用 app.domain.llm_client.LLMClient.simple_chat。
    """
    try:
        from app.domain.llm_client import LLMClient
        from app.core.config import Settings
    except Exception:
        return 0.5

    # 检查是否有任何 provider 已配置(简化: 看任一常见 env)
    if not any(
        os.environ.get(k)
        for k in ("OPENAI_API_KEY", "DEEPSEEK_API_KEY", "MINIMAX_API_KEY", "KIMI_API_KEY")
    ):
        return 0.5

    try:
        client = LLMClient(Settings())
        if not client.available_providers():
            return 0.5
        prompt = (
            "你是 GEO 输出质量评审。请对以下 agent 回复按 0-1 打分(越高越好)。\n\n"
            f"用户问题: {query}\n\n"
            f"期望关键词: {expected}\n\n"
            f"agent 回复: {response[:1500]}\n\n"
            "评分维度: 关键词覆盖 + 工具调用合理性 + 回答简洁性 + 不编造。\n"
            "只输出一个 0-1 之间的数字(如 0.75),不要解释。"
        )
        score_text = await client.simple_chat(prompt)
        score = float(score_text.strip().split()[0])
        return max(0.0, min(1.0, score))
    except Exception:
        return 0.5


async def judge(query: str, response: str, expected_keywords: list[str], expected_tool: str | None = None) -> JudgeResult:
    """评分主入口。"""
    kw = _keyword_score(response, expected_keywords)
    tl = _tool_score(response, expected_tool)
    ll = await _llm_score(query, response, expected_keywords)

    # 无 LLM 能力时(llm=0.5 中性),关键词+工具占 0.8/0.5 权重
    has_llm = ll != 0.5
    if has_llm:
        score = 0.5 * kw + 0.3 * tl + 0.2 * ll
    else:
        score = (0.6 * kw + 0.4 * tl) if expected_tool else kw

    return JudgeResult(
        pass_=score >= 0.5,
        score=score,
        keyword_score=kw,
        tool_score=tl,
        llm_score=ll,
        reason=f"keyword={kw:.2f} tool={tl:.2f} llm={ll:.2f} has_llm={has_llm}",
    )


__all__ = ["JudgeResult", "judge"]