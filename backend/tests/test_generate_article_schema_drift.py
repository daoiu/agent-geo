"""schema drift 防护测试: generate_article 工具 schema 必须与 v0.6 P1.6 行为对齐。

v0.6 P1.6+ 默认走后台任务（无需用户确认，article_count=1）。
老描述"生成前会向用户确认" 已与实际行为不符（docs/review/02-tool-boundary.md §3.5）。

依据: docs/superpowers/specs/2026-07-14-geo2-upgrade-design.md §3 阶段 1 P0#4。
"""
from __future__ import annotations

from app.domain.agent.tools import ToolName, _TOOL_SCHEMAS


def _generate_schema() -> dict:
    """通过 ToolName 枚举拿到 _GENERATE_SCHEMA(避免直接访问私有名)。"""
    return _TOOL_SCHEMAS[ToolName.GENERATE_ARTICLE.value]


def test_generate_article_schema_name() -> None:
    """生成工具名仍是 generate_article(契约稳定)。"""
    assert _generate_schema()["name"] == "generate_article"


def test_generate_article_describes_v06_background_path() -> None:
    """v0.6 P1.6+ 默认走后台路径,描述必须包含"后台"或"不询问"或"无需确认"语义。"""
    desc = _generate_schema()["description"]
    keywords = ("后台", "不询问", "无需确认")
    assert any(kw in desc for kw in keywords), (
        f"description 与 v0.6 行为 drift: 必须包含 {keywords} 之一;实际: {desc!r}"
    )


def test_generate_article_drops_old_human_confirmation_phrase() -> None:
    """老描述「生成前会向用户确认」已废弃,新 schema 不应再出现。"""
    desc = _generate_schema()["description"]
    assert "生成前会向用户确认" not in desc, (
        "description 仍含已废弃的'生成前会向用户确认'字样: " + repr(desc)
    )


def test_generate_article_required_params_unchanged() -> None:
    """Pydantic 必填参数契约不变(kb_id / brand / topic / keywords)。"""
    required = set(_generate_schema()["parameters"]["required"])
    assert required == {"kb_id", "brand", "topic", "keywords"}