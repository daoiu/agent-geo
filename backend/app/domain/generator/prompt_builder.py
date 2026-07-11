"""Build the user-role prompt for ContentWriterAgent.

角色指令 / 风格 / 反编造规则等系统级约束由
`app.domain.generator.system_prompts.build_content_writer_system_prompt`
负责（独立 system role）。本模块只构造 user-role 提示词：
主题 + 关键词 + 风格 + 字数 + 参考资料 + 字数约束等具体任务参数。
"""
from __future__ import annotations


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


def build_user_prompt(
    topic: str,
    keywords: list[str],
    target_length: int,
    chunks: list[dict],
) -> str:
    """Build the user-role prompt for one article generation call.

    与 v0.5 的差异：
    - 不再嵌入角色指令（"你是 X 的内容编辑"），那部分迁到 system role
    - 不再传 style（风格也由 system role 决定）
    - 不再传 brand（品牌信息也由 system role 注入）
    - 保留：主题 / 关键词 / 字数 / 参考资料 / BLUF 结构约束
    """
    chunks_block = _format_chunks(chunks)
    keywords_block = _format_keywords(keywords)

    return f"""请基于以下任务参数撰写一篇文章。

【主题】{topic}
【关键词】{keywords_block}
【目标字数】约 {target_length} 字（±20%）

【参考资料】（请基于这些真实信息撰写，不得编造参考资料中没有的事实）
---
{chunks_block}
---

要求：
1. 文章结构：标题（H1）、2-4 句引言、3-5 个 H2 章节（每节先给结论再展开）、结论
2. 引用参考资料时用 [1] [2] 等标注
3. 不得编造参考资料中没有的数据、价格、案例
4. 输出纯 Markdown，不要前置说明、不要代码块包裹整篇文章
"""


# ===========================================================================
# 向后兼容 shim（v0.5 接口）
# ===========================================================================
# 旧的 ContentWriter.write_article 仍可能 import `build`。
# 这里提供一个兼容层：把旧签名 (brand/topic/keywords/style/target_length/chunks)
# 直接拼成一个 user prompt（旧实现就是把角色指令嵌 user 里）。
# 新代码应使用 build_user_prompt + build_content_writer_system_prompt 组合。
# ===========================================================================


def build(
    brand: str | None,
    topic: str,
    keywords: list[str],
    style: str,
    target_length: int,
    chunks: list[dict],
) -> str:
    """v0.5 兼容：旧 ContentWriter.write_article 仍在用。返回 user prompt（含旧角色指令）。"""
    from app.domain.generator.system_prompts import _style_label

    style_label = _style_label(style)
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
