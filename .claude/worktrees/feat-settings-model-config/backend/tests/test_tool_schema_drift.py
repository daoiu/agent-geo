"""全工具 schema drift 防护测试（P1#10 / Task 11）。

基于 P0#4 的 generate_article schema drift 测试扩展到全部 5 个工具：
- diagnose_brand / search / generate_article / list_knowledge_bases / create_generation_task

每个工具断言：
1. 结构完整：name / description / parameters.required / parameters.properties
2. description 包含关键行为词（与实际代码对齐，不漂移）
3. 必填参数集合稳定（契约不变）
4. description 不能含已废弃的旧措辞（如"生成前会向用户确认"）

失败意味着 schema 与 v0.6 实际行为不一致，需同步 tools.py + 可能要重训 prompt。
"""
from __future__ import annotations

import pytest

from app.domain.agent.tools import _TOOL_SCHEMAS, ToolName


def _schema(tool: str) -> dict:
    return _TOOL_SCHEMAS[tool]


def _desc(tool: str) -> str:
    return _schema(tool)["description"]


# ===========================================================================
# 全工具通用契约
# ===========================================================================


ALL_TOOL_NAMES = [
    ToolName.DIAGNOSE_BRAND.value,
    ToolName.SEARCH_KNOWLEDGE.value,
    ToolName.GENERATE_ARTICLE.value,
    ToolName.LIST_KNOWLEDGE_BASES.value,
    ToolName.CREATE_GENERATION_TASK.value,
]


@pytest.mark.parametrize("tool_name", ALL_TOOL_NAMES)
def test_all_tools_have_required_top_level_fields(tool_name: str) -> None:
    """每个工具 schema 必须有 name / description / parameters。"""
    s = _schema(tool_name)
    assert "name" in s, f"{tool_name} 缺 name"
    assert "description" in s, f"{tool_name} 缺 description"
    assert "parameters" in s, f"{tool_name} 缺 parameters"
    assert isinstance(s["description"], str) and len(s["description"]) > 10, (
        f"{tool_name} description 太短或非字符串：{s['description']!r}"
    )


@pytest.mark.parametrize("tool_name", ALL_TOOL_NAMES)
def test_all_tools_parameters_have_type_object(tool_name: str) -> None:
    """每个工具的 parameters.type 必须是 'object'（OpenAI 协议要求）。"""
    s = _schema(tool_name)
    assert s["parameters"]["type"] == "object", (
        f"{tool_name} parameters.type 必须是 'object'，实际：{s['parameters']['type']!r}"
    )


@pytest.mark.parametrize("tool_name", ALL_TOOL_NAMES)
def test_all_tools_required_params_exist_in_properties(tool_name: str) -> None:
    """required 数组中的每个字段必须在 properties 中定义。"""
    s = _schema(tool_name)
    required = set(s["parameters"].get("required", []))
    properties = set(s["parameters"].get("properties", {}).keys())
    missing = required - properties
    assert not missing, f"{tool_name} required 字段 {missing} 不在 properties 中"


# ===========================================================================
# 各工具特定行为词断言（防 schema 与实际行为 drift）
# ===========================================================================


def test_diagnose_brand_describes_diagnosis_purpose() -> None:
    """diagnose_brand 描述必须含诊断语义。"""
    desc = _desc(ToolName.DIAGNOSE_BRAND.value)
    assert any(kw in desc for kw in ("诊断", "健康度", "分数", "GEO")), (
        f"diagnose_brand description 缺诊断关键词：{desc!r}"
    )


def test_search_describes_retrieval_purpose() -> None:
    """search_knowledge 描述必须含检索语义。"""
    desc = _desc(ToolName.SEARCH_KNOWLEDGE.value)
    assert any(kw in desc for kw in ("检索", "知识库", "片段", "搜索")), (
        f"search_knowledge description 缺检索关键词：{desc!r}"
    )


def test_generate_article_describes_v06_background_path() -> None:
    """generate_article v0.6 P1.6+ 默认走后台，描述必须含后台/无需确认语义。"""
    desc = _desc(ToolName.GENERATE_ARTICLE.value)
    keywords = ("后台", "不询问", "无需确认")
    assert any(kw in desc for kw in keywords), (
        f"generate_article description 与 v0.6 行为 drift：必须含 {keywords} 之一；"
        f"实际：{desc!r}"
    )


def test_generate_article_drops_old_human_confirmation_phrase() -> None:
    """已废弃的「生成前会向用户确认」字样必须不再出现。"""
    desc = _desc(ToolName.GENERATE_ARTICLE.value)
    assert "生成前会向用户确认" not in desc, (
        "description 仍含已废弃字样：" + repr(desc)
    )


def test_list_knowledge_bases_describes_listing_purpose() -> None:
    """list_knowledge_bases 描述必须含列表语义。"""
    desc = _desc(ToolName.LIST_KNOWLEDGE_BASES.value)
    assert any(kw in desc for kw in ("列出", "可用", "知识库", "列表")), (
        f"list_knowledge_bases description 缺列表关键词：{desc!r}"
    )


def test_create_generation_task_describes_batch_purpose() -> None:
    """create_generation_task 描述必须含批量/任务/后台语义（v0.6 P1.6+ 走异步任务）。"""
    desc = _desc(ToolName.CREATE_GENERATION_TASK.value)
    keywords = ("批量", "任务", "后台", "异步")
    assert any(kw in desc for kw in keywords), (
        f"create_generation_task description 缺任务关键词：{desc!r}"
    )


# ===========================================================================
# 必填参数契约（防契约漂移）
# ===========================================================================


def test_diagnose_brand_required_params() -> None:
    """diagnose_brand 必填：brand_name / industry / official_url（核心三要素）。"""
    required = set(_schema(ToolName.DIAGNOSE_BRAND.value)["parameters"]["required"])
    assert required == {"brand_name", "industry", "official_url"}, (
        f"diagnose_brand required 漂移：{required}"
    )


def test_search_required_params() -> None:
    """search_knowledge 必填：query（其他 top_k 可选）。"""
    required = set(_schema(ToolName.SEARCH_KNOWLEDGE.value)["parameters"]["required"])
    assert "query" in required, f"search_knowledge 必填 query：{required}"


def test_generate_article_required_params() -> None:
    """generate_article 必填：kb_id / brand / topic / keywords。"""
    required = set(_schema(ToolName.GENERATE_ARTICLE.value)["parameters"]["required"])
    assert required == {"kb_id", "brand", "topic", "keywords"}, (
        f"generate_article required 漂移：{required}"
    )


def test_create_generation_task_required_params() -> None:
    """create_generation_task 必填：kb_id / brand / topic / keywords + article_count（批量生成必填数量）。"""
    required = set(_schema(ToolName.CREATE_GENERATION_TASK.value)["parameters"]["required"])
    assert required == {"kb_id", "brand", "topic", "keywords", "article_count"}, (
        f"create_generation_task required 漂移：{required}"
    )


def test_list_knowledge_bases_no_required_params() -> None:
    """list_knowledge_bases 无必填参数（只是列表）。"""
    required = set(_schema(ToolName.LIST_KNOWLEDGE_BASES.value)["parameters"]["required"])
    assert required == set(), f"list_knowledge_bases 不应有 required：{required}"


# ===========================================================================
# 已废弃措辞扫描（全工具，防止任意工具回退到旧描述）
# ===========================================================================


DEPRECATED_PHRASES = (
    "生成前会向用户确认",  # 老 generate_article 行为
    "可能会调用",  # 模糊描述，stage 1 锐评要求明确
    "请谨慎使用",  # 模糊告警语
)


@pytest.mark.parametrize("tool_name", ALL_TOOL_NAMES)
@pytest.mark.parametrize("phrase", DEPRECATED_PHRASES)
def test_no_tool_uses_deprecated_phrases(tool_name: str, phrase: str) -> None:
    """全工具不应含已废弃描述短语。"""
    desc = _desc(tool_name)
    assert phrase not in desc, (
        f"{tool_name} description 含已废弃短语 {phrase!r}：{desc!r}"
    )