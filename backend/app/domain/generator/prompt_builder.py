"""Build prompts for article generation grounded in knowledge base chunks."""
from __future__ import annotations

_STYLE_LABELS = {
    "neutral": "中性客观",
    "professional": "专业严谨",
    "casual": "轻松活泼",
}


def _format_chunks(chunks: list[dict]) -> str:
    if not chunks:
        return (
            "（知识库暂无可用参考资料。请基于通用知识撰写，但避免编造具体数据/价格/案例。）"
        )
    parts: list[str] = []
    for c in chunks:
        idx = c.get("index", 0)
        content = c.get("content", "").strip()
        parts.append(f"[参考资料 #{idx}]\n{content}")
    return "\n\n".join(parts)


def _format_keywords(keywords: list[str]) -> str:
    if not keywords:
        return "（无）"
    return "、".join(keywords)


def build(
    brand: str | None,
    topic: str,
    keywords: list[str],
    style: str,
    target_length: int,
    chunks: list[dict],
) -> str:
    """Build the article-generation prompt.

    Returns a string that, when sent to an LLM, instructs it to write a
    Markdown article grounded in the provided chunks. Includes explicit
    anti-fabrication instructions.
    """
    style_label = _STYLE_LABELS.get(style, style)
    brand_phrase = brand or "该品牌"
    chunks_block = _format_chunks(chunks)
    keywords_block = _format_keywords(keywords)

    return f"""你是 {brand_phrase} 的内容编辑。基于以下"参考资料"撰写一篇文章。

【主题】{topic}
【关键词】{keywords_block}
【风格】{style_label}
【目标字数】约 {target_length} 字

【参考资料】（请基于这些真实信息撰写，不得编造参考资料中没有的事实）
---
{chunks_block}
---

要求：
1. 文章结构：标题（H1）、引言、3-5 个 H2 章节、结论
2. 每段开头直接给出核心主张（BLUF 原则）
3. 引用参考资料时用 [1] [2] 等标注
4. 不得编造参考资料中没有的数据、价格、案例
5. 不得使用"作为 AI 模型"等元话语

输出 Markdown 格式。
"""
