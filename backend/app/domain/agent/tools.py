"""v0.4 Agent 工具定义：function calling schema + Pydantic 参数校验。

工具集（v0.6 P1.4 起 5 个）：
- diagnose_brand：v0.1 诊断（读，包装 DiagnosisService）
- search_knowledge：知识库检索（读，kb_id 可选：传=单库 v0.5 hybrid / 不传=跨库 P1.3）
- generate_article：v0.2 单篇文章生成（写，包装 ContentWriter，需 human 确认，仅返回预览）
- list_knowledge_bases：列出所有知识库（读，含 doc_count，供 LLM 发现可用品牌库）
- create_generation_task：批量生成任务（写，包装 v0.2 TaskRepository，不需确认）

OpenAI Function Calling 协议兼容 DeepSeek / Kimi。
"""
from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field, HttpUrl


class ToolName(str, Enum):
    """五个工具的稳定名称。"""

    DIAGNOSE_BRAND = "diagnose_brand"
    SEARCH_KNOWLEDGE = "search_knowledge"
    GENERATE_ARTICLE = "generate_article"
    LIST_KNOWLEDGE_BASES = "list_knowledge_bases"
    CREATE_GENERATION_TASK = "create_generation_task"


# ---------------------------------------------------------------------------
# Pydantic 参数校验模型
# ---------------------------------------------------------------------------


class DiagnoseBrandArgs(BaseModel):
    """diagnose_brand 工具的参数。"""

    brand_name: str = Field(..., min_length=1, max_length=100)
    industry: str = Field(..., min_length=1, max_length=100)
    official_url: HttpUrl


class SearchKnowledgeArgs(BaseModel):
    """search_knowledge 工具的参数 (v0.6 P1.4: kb_id 可选)."""

    kb_id: str | None = Field(None, min_length=1)  # 不传=跨库 (P1.3)
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


class ListKnowledgeBasesArgs(BaseModel):
    """list_knowledge_bases 工具的参数（无参，工具签名占位）."""

    # Pydantic model 必须继承 BaseModel 但允许 0 字段（OpenAI schema 的空 properties）。
    model_config = {"extra": "forbid"}


class CreateGenerationTaskArgs(BaseModel):
    """create_generation_task 工具的参数（v0.6 P1.4 — 包装 v0.2 TaskCreate）.

    与 app.models.task.TaskCreate 对齐，但去掉 name（前端的 name 会从
    brand+topic 自动拼接生成，避免 LLM 多写一个不必要字段）。
    """

    kb_id: str = Field(..., min_length=1)
    brand: str = Field(..., min_length=1, max_length=100)
    topic: str = Field(..., min_length=5, max_length=500)
    keywords: list[str] = Field(..., min_length=1, max_length=20)
    article_count: int = Field(5, ge=1, le=20)
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
        "在指定知识库或全局搜索与查询相关的资料片段。"
        "kb_id 不传或 null 时，跨所有知识库做 hybrid 召回（向量 + 关键词 + RRF）。"
        "kb_id 传时则限定该 KB 召回。返回最相关的几个资料片段 "
        "（含 KB 名称、来源文档、向量/关键词命中来源标签）。"
        "agent 只能查询已存在的知识库，不能创建/修改/删除。"
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "kb_id": {
                "type": "string",
                "description": (
                    "知识库 ID（UUID）；不传则跨所有知识库全局检索。"
                ),
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
        "required": ["query"],
    },
}


_GENERATE_SCHEMA: dict = {
    "name": "generate_article",
    "description": (
        "基于指定知识库生成一篇文章草稿。"
        "v0.6 P1.6+ 默认走后台任务（无需用户确认，内部 article_count=1），"
        "返回 task_id，用户可在 /tasks/{task_id} 审核。"
        "例外：用户明确说'实时预览'才走老 HumanConfirmation 路径（暂未启用）。"
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


_LIST_SCHEMA: dict = {
    "name": "list_knowledge_bases",
    "description": (
        "列出所有已创建的知识库，返回 [{kb_id, kb_name, doc_count, created_at}]。"
        "在用户模糊提问（如「我有哪些品牌资料库」「有哪些品牌」）或 LLM 不知道该查哪个 KB 时调用。"
        "调用 search_knowledge 之前也应该先调这个工具确认 kb_id 存在。"
    ),
    "parameters": {
        "type": "object",
        "properties": {},
        "required": [],
    },
}


_CREATE_TASK_SCHEMA: dict = {
    "name": "create_generation_task",
    "description": (
        "创建一个内容生成任务（v0.2 TaskCreator），用 kb_id 指定的 KB 内容生成 N 篇文章草稿。"
        "返回 task_id。生成 + 审核 + 发布由 v0.2 任务系统负责，"
        "agent 这里只需要触发任务即可，**不需要在会话内循环**。"
        "生成的 N 篇文章在 /tasks/{task_id} 详情页审核 → 发布。"
        "适用：用户说「给我生成 X 品牌 N 篇文章」「批量生成 X 文章」，N>1 时务必用这个工具。"
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "kb_id": {
                "type": "string",
                "description": "知识库 ID（UUID）",
            },
            "brand": {
                "type": "string",
                "description": "目标品牌名",
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
            "article_count": {
                "type": "integer",
                "description": "生成文章数量，默认 5，最大 20",
                "default": 5,
            },
            "style": {
                "type": "string",
                "enum": ["neutral", "professional", "casual"],
                "description": "写作风格，默认 neutral",
                "default": "neutral",
            },
            "target_length": {
                "type": "integer",
                "description": "每篇目标字数，默认 1500",
                "default": 1500,
            },
        },
        "required": ["kb_id", "brand", "topic", "keywords", "article_count"],
    },
}


# ---------------------------------------------------------------------------
# 公共导出
# ---------------------------------------------------------------------------


TOOLS: list[dict] = [
    {"type": "function", "function": _DIAGNOSE_SCHEMA},
    {"type": "function", "function": _SEARCH_SCHEMA},
    {"type": "function", "function": _GENERATE_SCHEMA},
    {"type": "function", "function": _LIST_SCHEMA},
    {"type": "function", "function": _CREATE_TASK_SCHEMA},
]


TOOL_NAMES: set[str] = {
    ToolName.DIAGNOSE_BRAND.value,
    ToolName.SEARCH_KNOWLEDGE.value,
    ToolName.GENERATE_ARTICLE.value,
    ToolName.LIST_KNOWLEDGE_BASES.value,
    ToolName.CREATE_GENERATION_TASK.value,
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
    "list_knowledge_bases": ListKnowledgeBasesArgs,
    "create_generation_task": CreateGenerationTaskArgs,
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


# ---------------------------------------------------------------------------
# v0.6+ P1#13（Task 14）：声明式权限元数据
# ---------------------------------------------------------------------------
#
# 每个工具的权限/副作用/成本/幂等性集中声明，便于：
# 1. ToolExecutor/HITL 决策不再硬编码 if/elif
# 2. 未来加工具只需登记元数据，无需改 dispatch
# 3. UI / 审计可查 side_effect / category 决定展示
#
# 字段说明：
# - requires_confirmation: bool — 是否需要 HumanConfirmation 才能执行
# - category: 'read'|'write'|'admin' — 业务分类
# - side_effect: bool — 是否修改外部状态（DB / 文件 / 邮件）
# - is_idempotent: bool — 重复调用结果是否相同
# - estimated_cost_tier: 'low'|'medium'|'high' — LLM/算力成本量级
#
# v0.6 P1.6+ 行为变更：generate_article 走后台任务，不再抛 HumanConfirmation。
_TOOL_PERMISSIONS: dict[str, dict] = {
    "diagnose_brand": {
        "requires_confirmation": False,
        "category": "read",
        "side_effect": False,
        "is_idempotent": True,
        "estimated_cost_tier": "low",
    },
    "search_knowledge": {
        "requires_confirmation": False,
        "category": "read",
        "side_effect": False,
        "is_idempotent": True,
        "estimated_cost_tier": "low",
    },
    "generate_article": {
        "requires_confirmation": False,  # v0.6 P1.6+ 走后端任务，无需用户确认
        "category": "write",
        "side_effect": True,
        "is_idempotent": False,
        "estimated_cost_tier": "high",
    },
    "list_knowledge_bases": {
        "requires_confirmation": False,
        "category": "read",
        "side_effect": False,
        "is_idempotent": True,
        "estimated_cost_tier": "low",
    },
    "create_generation_task": {
        "requires_confirmation": False,  # v0.6 P1.6+ 也走后台任务
        "category": "write",
        "side_effect": True,
        "is_idempotent": False,
        "estimated_cost_tier": "high",
    },
}


def get_tool_permission(tool_name: str) -> dict:
    """按名称获取工具权限声明。

    Raises:
        ValueError: 未知的工具名。
    """
    if tool_name not in _TOOL_PERMISSIONS:
        raise ValueError(f"Unknown tool: {tool_name}")
    return _TOOL_PERMISSIONS[tool_name]


def requires_confirmation(tool_name: str) -> bool:
    """便捷查询：工具是否需要 HumanConfirmation 才能执行（声明式）。

    Raises:
        ValueError: 未知的工具名。
    """
    return get_tool_permission(tool_name)["requires_confirmation"]