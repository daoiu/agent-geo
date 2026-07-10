"""v0.4 Agent 工具定义：function calling schema + Pydantic 参数校验。

工具集（3 个）：
- diagnose_brand：v0.1 诊断（读，包装 DiagnosisService）
- search_knowledge：v0.2 知识库检索（读，包装 KnowledgeRepository，chunk 截断 500 字）
- generate_article：v0.2 文章生成（写，包装 ContentWriter，需 human 确认，仅返回预览）

OpenAI Function Calling 协议兼容 DeepSeek / Kimi。
"""
from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field, HttpUrl


class ToolName(str, Enum):
    """三个工具的稳定名称。"""

    DIAGNOSE_BRAND = "diagnose_brand"
    SEARCH_KNOWLEDGE = "search_knowledge"
    GENERATE_ARTICLE = "generate_article"


# ---------------------------------------------------------------------------
# Pydantic 参数校验模型
# ---------------------------------------------------------------------------


class DiagnoseBrandArgs(BaseModel):
    """diagnose_brand 工具的参数。"""

    brand_name: str = Field(..., min_length=1, max_length=100)
    industry: str = Field(..., min_length=1, max_length=100)
    official_url: HttpUrl


class SearchKnowledgeArgs(BaseModel):
    """search_knowledge 工具的参数。"""

    kb_id: str = Field(..., min_length=1)
    query: str = Field(..., min_length=1, max_length=500)
    limit: int = Field(5, ge=1, le=10)  # 默认 5，最大 10（与 schema 描述一致）


class GenerateArticleArgs(BaseModel):
    """generate_article 工具的参数。"""

    kb_id: str = Field(..., min_length=1)
    brand: str = Field(..., min_length=1, max_length=100)
    topic: str = Field(..., min_length=5, max_length=500)
    keywords: list[str] = Field(..., min_length=1, max_length=20)
    style: Literal["neutral", "professional", "casual"] = "neutral"
    target_length: int = Field(1500, ge=300, le=10000)


# ---------------------------------------------------------------------------
# OpenAI Function Calling schema（发给 LLM）
# ---------------------------------------------------------------------------


_DIAGNOSE_SCHEMA: dict = {
    "name": "diagnose_brand",
    "description": (
        "对一个品牌执行 GEO 健康度诊断。需要品牌的名称、行业和官网 URL。"
        "返回综合分数（0-100）、5 个维度的子分数、诊断报告 ID、可能还包括建议清单摘要。"
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "brand_name": {
                "type": "string",
                "description": "品牌名称，如 '小米'",
            },
            "industry": {
                "type": "string",
                "description": "品牌所属行业，如 '消费电子'",
            },
            "official_url": {
                "type": "string",
                "description": (
                    "品牌官网 URL，如 'https://www.mi.com'，"
                    "必须以 http:// 或 https:// 开头"
                ),
            },
        },
        "required": ["brand_name", "industry", "official_url"],
    },
}


_SEARCH_SCHEMA: dict = {
    "name": "search_knowledge",
    "description": (
        "在指定知识库中搜索与查询相关的资料片段。需要知识库 ID 和搜索关键词。"
        "返回最相关的几个资料片段（含内容）。注意：agent 只能查询已存在的知识库，"
        "不能创建/修改/删除。"
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "kb_id": {
                "type": "string",
                "description": "知识库 ID（UUID）",
            },
            "query": {
                "type": "string",
                "description": "搜索关键词或问题",
            },
            "limit": {
                "type": "integer",
                "description": "返回几个片段，默认 5，最大 10",
                "default": 5,
            },
        },
        "required": ["kb_id", "query"],
    },
}


_GENERATE_SCHEMA: dict = {
    "name": "generate_article",
    "description": (
        "基于指定知识库生成一篇文章草稿。生成前会向用户确认。"
        "返回的内容仅供预览，正式发布需要用户去 v0.2 任务列表完成完整任务流程"
        "（创建任务 → 生成 → 审核 → 发布）。"
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "kb_id": {
                "type": "string",
                "description": "知识库 ID",
            },
            "brand": {
                "type": "string",
                "description": "品牌名",
            },
            "topic": {
                "type": "string",
                "description": "文章主题（至少 5 个字）",
            },
            "keywords": {
                "type": "array",
                "items": {"type": "string"},
                "description": "关键词（至少 1 个）",
            },
            "style": {
                "type": "string",
                "enum": ["neutral", "professional", "casual"],
                "description": "写作风格，默认 neutral",
                "default": "neutral",
            },
            "target_length": {
                "type": "integer",
                "description": "目标字数，默认 1500",
                "default": 1500,
            },
        },
        "required": ["kb_id", "brand", "topic", "keywords"],
    },
}


# ---------------------------------------------------------------------------
# 公共导出
# ---------------------------------------------------------------------------


TOOLS: list[dict] = [
    {"type": "function", "function": _DIAGNOSE_SCHEMA},
    {"type": "function", "function": _SEARCH_SCHEMA},
    {"type": "function", "function": _GENERATE_SCHEMA},
]


TOOL_NAMES: set[str] = {
    ToolName.DIAGNOSE_BRAND.value,
    ToolName.SEARCH_KNOWLEDGE.value,
    ToolName.GENERATE_ARTICLE.value,
}


_TOOL_SCHEMAS: dict[str, dict] = {t["function"]["name"]: t["function"] for t in TOOLS}


def get_tool_schema(tool_name: str) -> dict:
    """按名称获取 function calling schema。

    Raises:
        ValueError: 未知的工具名。
    """
    if tool_name not in _TOOL_SCHEMAS:
        raise ValueError(f"Unknown tool: {tool_name}")
    return _TOOL_SCHEMAS[tool_name]


# 参数校验器映射
_VALIDATORS: dict[str, type[BaseModel]] = {
    "diagnose_brand": DiagnoseBrandArgs,
    "search_knowledge": SearchKnowledgeArgs,
    "generate_article": GenerateArticleArgs,
}


def validate_tool_args(tool_name: str, args: dict) -> BaseModel:
    """用对应的 Pydantic 模型校验 LLM 提供的工具参数。

    Returns:
        校验后的 Pydantic 模型实例。

    Raises:
        ValueError: 未知工具名。
        pydantic.ValidationError: 参数不符合 schema。
    """
    if tool_name not in _VALIDATORS:
        raise ValueError(f"Unknown tool: {tool_name}")
    return _VALIDATORS[tool_name](**args)