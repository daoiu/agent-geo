"""查询改写:Multi-Query 扩写 + 可选 HyDE。无 LLM key 时降级为原查询。

提供 _parse_lines / _multi_query / _hyde 三个内部函数,均接受 duck-typed llm
(只要有 simple_chat + available_providers 即可,便于单测注入 FakeLLM)。
"""
from __future__ import annotations

import re

import structlog

logger = structlog.get_logger()
# 匹配常见行首编号:`1.` `1)` `1、` 或 `-`/`*` 短横前缀
_NUM_PREFIX = re.compile(r"^\s*(?:\d+[.)、]|[-*])\s*")


def _parse_lines(reply: str) -> list[str]:
    """按行拆分 LLM 回复,剥编号前缀、去空行,返回非空字符串列表。"""
    out: list[str] = []
    for line in reply.splitlines():
        s = _NUM_PREFIX.sub("", line).strip()
        if s:
            out.append(s)
    return out


async def _multi_query(query: str, llm, n: int) -> list[str]:
    """让 LLM 改写出 n 条语义等价但措辞不同的中文查询。"""
    prompt = (
        f"把下面的检索问题改写成 {n} 条语义等价但措辞不同的中文查询,每行一条,不要编号:\n{query}"
    )
    return _parse_lines(await llm.simple_chat(prompt))[:n]


async def _hyde(query: str, llm) -> str:
    """HyDE:让 LLM 写一段 2-3 句的假设答案,作为额外检索 query。"""
    prompt = f"针对问题写一段 2-3 句、像知识库文档的假设答案,只输出内容:\n{query}"
    return (await llm.simple_chat(prompt)).strip()


async def rewrite(query: str, llm, n: int = 3, enable_hyde: bool = False) -> list[str]:
    """主入口:返回 [原查询, 改写1..n, (HyDE 假设文档)]。

    - 无 provider → 降级返回 [query]
    - LLM 异常 → 降级返回已有 variants(至少含原查询)
    - 结果去重保序
    """
    if not getattr(llm, "available_providers", []):
        return [query]
    variants = [query]
    try:
        variants.extend(await _multi_query(query, llm, n))
        if enable_hyde:
            doc = await _hyde(query, llm)
            if doc:
                variants.append(doc)
    except Exception as e:  # noqa: BLE001
        logger.warning("query_rewrite_failed", error=str(e))
    # 去重保序
    seen: set[str] = set()
    out: list[str] = []
    for v in variants:
        if v and v not in seen:
            seen.add(v)
            out.append(v)
    return out