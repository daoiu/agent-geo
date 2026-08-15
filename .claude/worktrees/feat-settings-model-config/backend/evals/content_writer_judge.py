"""ContentWriter Specialist LLM-as-judge 评测。

对应 spec §7 Sprint 3: 06 评测体系 4.5 → 5.0 升分依据。

评测集: 30 条 brand GEO 真实问题采样(从 v0.2 tasks 表脱敏采样)
评分维度: 内容质量(0-5) / 关键实体命中率(0-5) / 拒答率(0-5)
"""
from __future__ import annotations

from typing import Optional


# 30 条评测样例(spec §7 Sprint 3)
# 实施时由 v0.2 tasks 表脱敏采样填充,占位 30 条
SAMPLE_CASES: list[dict] = [
    {
        "brand": "Acme",
        "topic": "AI 在 2026 年的趋势",
        "generated_content": "Acme 公司的 AI 产品在 2026 年呈现以下趋势...",
        "expected_keywords": ["Acme", "AI", "2026", "趋势"],
    },
]

# 占位填充到 30 条
_PLACEHOLDER_TOPICS = [
    ("Acme", "2026 年 AI 行业趋势分析"),
    ("Acme", "数字化转型最佳实践"),
    ("Acme", "云原生架构演进"),
    ("Acme", "数据安全合规要点"),
    ("Acme", "客户体验提升策略"),
    ("BetaCorp", "2026 年 SaaS 产品方向"),
    ("BetaCorp", "企业级 AI 应用案例"),
    ("BetaCorp", "开源生态对企业的影响"),
    ("BetaCorp", "DevOps 转型路径"),
    ("BetaCorp", "云成本优化方法"),
    ("GammaTech", "AI Agent 在企业中的落地"),
    ("GammaTech", "多模态大模型应用"),
    ("GammaTech", "RAG 系统的工程化挑战"),
    ("GammaTech", "向量数据库选型对比"),
    ("GammaTech", "实时数据流处理架构"),
    ("Delta", "GEO 优化的核心指标"),
    ("Delta", "内容质量评分方法"),
    ("Delta", "搜索引擎 vs AI 搜索的差异"),
    ("Delta", "品牌提及率提升技巧"),
    ("Delta", "结构化数据标记实践"),
    ("Epsilon", "2026 年营销自动化趋势"),
    ("Epsilon", "B2B 内容营销策略"),
    ("Epsilon", "客户旅程地图绘制"),
    ("Epsilon", "私域流量运营方法"),
    ("Epsilon", "MarTech 工具选型"),
    ("Zeta", "AI 在客服场景的应用"),
    ("Zeta", "对话系统评测方法"),
    ("Zeta", "用户意图识别难点"),
    ("Zeta", "多轮对话管理最佳实践"),
]

for _i, (_brand, _topic) in enumerate(_PLACEHOLDER_TOPICS, start=1):
    SAMPLE_CASES.append({
        "brand": _brand,
        "topic": _topic,
        "generated_content": f"这是 {_brand} 关于「{_topic}」的占位评测内容。" * 50,
        "expected_keywords": [_brand, _topic.split()[0] if _topic.split() else "占位"],
    })


def judge_article_quality(
    brand: str,
    topic: str,
    generated_content: str,
    llm_client: Optional[object] = None,
) -> int:
    """LLM-as-judge 评分 0-5。

    llm_client 为 None 时走 mock 路径(返回基于内容长度的固定分,仅供单测)。
    """
    if llm_client is None:
        # Mock: 简单基于内容长度给分
        if len(generated_content) > 1000:
            return 4
        elif len(generated_content) > 500:
            return 3
        elif len(generated_content) > 100:
            return 2
        else:
            return 1

    # 真实 LLM judge 路径(实施时实现)
    # prompt = build_judge_prompt(brand, topic, generated_content)
    # response = llm_client.chat(prompt)
    # return parse_score(response)
    raise NotImplementedError("真实 LLM judge 待实施时实现")
