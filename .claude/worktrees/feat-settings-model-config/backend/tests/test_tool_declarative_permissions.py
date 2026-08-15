"""验证声明式权限元数据（P1#13 / Task 14）。

行为契约：
- 每个工具在 _TOOL_PERMISSIONS 中声明权限元数据
- 元数据字段: requires_confirmation / category / side_effect / is_idempotent / estimated_cost_tier
- get_tool_permission(tool_name) 返回声明
- requires_confirmation(tool_name) 便捷查询
- 未知工具名抛 ValueError

v0.6 P1.6+ 行为：所有 5 个工具 requires_confirmation=False（生成类走后台任务）。
"""
from __future__ import annotations

import pytest

from app.domain.agent.tools import (
    TOOL_NAMES,
    ToolName,
    get_tool_permission,
    requires_confirmation,
)


ALL_TOOLS = [
    ToolName.DIAGNOSE_BRAND.value,
    ToolName.SEARCH_KNOWLEDGE.value,
    ToolName.GENERATE_ARTICLE.value,
    ToolName.LIST_KNOWLEDGE_BASES.value,
    ToolName.CREATE_GENERATION_TASK.value,
]


# ===========================================================================
# 通用契约：每个工具必须有元数据
# ===========================================================================


@pytest.mark.parametrize("tool_name", ALL_TOOLS)
def test_every_tool_has_permission_metadata(tool_name: str) -> None:
    """每个工具都必须在 _TOOL_PERMISSIONS 中声明。"""
    perm = get_tool_permission(tool_name)
    assert isinstance(perm, dict), f"{tool_name} 权限声明必须是 dict"
    # 必填字段
    assert "requires_confirmation" in perm
    assert "category" in perm
    assert "side_effect" in perm


@pytest.mark.parametrize("tool_name", ALL_TOOLS)
def test_requires_confirmation_is_boolean(tool_name: str) -> None:
    """requires_confirmation 必须是 bool。"""
    assert isinstance(requires_confirmation(tool_name), bool)


@pytest.mark.parametrize("tool_name", ALL_TOOLS)
def test_category_is_valid(tool_name: str) -> None:
    """category 必须是 read / write / admin 之一。"""
    perm = get_tool_permission(tool_name)
    assert perm["category"] in ("read", "write", "admin"), (
        f"{tool_name} category 必须是 read/write/admin,实际 {perm['category']!r}"
    )


@pytest.mark.parametrize("tool_name", ALL_TOOLS)
def test_side_effect_is_boolean(tool_name: str) -> None:
    """side_effect 必须是 bool。"""
    perm = get_tool_permission(tool_name)
    assert isinstance(perm["side_effect"], bool), (
        f"{tool_name} side_effect 必须是 bool"
    )


# ===========================================================================
# v0.6 P1.6+ 行为契约
# ===========================================================================


@pytest.mark.parametrize("tool_name", ALL_TOOLS)
def test_v06_all_tools_no_confirmation(tool_name: str) -> None:
    """v0.6 P1.6+: 所有 5 个工具都走后台/直执,无需确认。"""
    assert requires_confirmation(tool_name) is False, (
        f"{tool_name} 在 v0.6 P1.6+ 不应需要 HumanConfirmation"
    )


def test_read_tools_have_no_side_effect() -> None:
    """读类工具应无 side_effect。"""
    for tool in (ToolName.DIAGNOSE_BRAND.value, ToolName.SEARCH_KNOWLEDGE.value, ToolName.LIST_KNOWLEDGE_BASES.value):
        perm = get_tool_permission(tool)
        assert perm["category"] == "read", f"{tool} 应为 read 类别"
        assert perm["side_effect"] is False, f"{tool} 读类不应有 side_effect"


def test_write_tools_have_side_effect() -> None:
    """写类工具应有 side_effect=True。"""
    for tool in (ToolName.GENERATE_ARTICLE.value, ToolName.CREATE_GENERATION_TASK.value):
        perm = get_tool_permission(tool)
        assert perm["category"] == "write", f"{tool} 应为 write 类别"
        assert perm["side_effect"] is True, f"{tool} 写类应有 side_effect"


def test_write_tools_are_not_idempotent() -> None:
    """写类工具不可幂等（重复调用会创建多份）。"""
    for tool in (ToolName.GENERATE_ARTICLE.value, ToolName.CREATE_GENERATION_TASK.value):
        perm = get_tool_permission(tool)
        assert perm.get("is_idempotent") is False, (
            f"{tool} 写类工具不应标记为幂等"
        )


# ===========================================================================
# 错误路径
# ===========================================================================


def test_unknown_tool_raises_value_error() -> None:
    """未知工具名应抛 ValueError。"""
    with pytest.raises(ValueError):
        get_tool_permission("nonexistent_tool")


def test_requires_confirmation_unknown_tool_raises() -> None:
    """未知工具名查 requires_confirmation 也应抛 ValueError。"""
    with pytest.raises(ValueError):
        requires_confirmation("nonexistent_tool")


# ===========================================================================
# 元数据一致性：写类工具的 estimated_cost_tier 应 >= medium
# ===========================================================================


@pytest.mark.parametrize("tool_name", [ToolName.GENERATE_ARTICLE.value, ToolName.CREATE_GENERATION_TASK.value])
def test_write_tools_have_cost_tier(tool_name: str) -> None:
    """写类工具必须有 estimated_cost_tier 字段，且 >= medium。"""
    perm = get_tool_permission(tool_name)
    tier = perm.get("estimated_cost_tier")
    assert tier in ("medium", "high"), (
        f"{tool_name} 写类工具 estimated_cost_tier 应 >= medium,实际 {tier!r}"
    )


# ===========================================================================
# 与 TOOL_NAMES 同步（防止工具加进 TOOLS 但漏登记权限）
# ===========================================================================


def test_permission_metadata_covers_all_tool_names() -> None:
    """_TOOL_PERMISSIONS 必须覆盖 TOOL_NAMES 集合中的每个工具。"""
    for tool in TOOL_NAMES:
        # 不抛异常即存在
        get_tool_permission(tool)