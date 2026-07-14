"""P2#35（Task 43）: 工具注册表收拢测试。

目标:
- 统一注册表(TOOL_REGISTRY) 包含 schema/validator/permission/executor
- 单点查 TOOL_REGISTRY[tool_name] 可拿全部信息
- 向后兼容:旧 API(get_tool_schema/validate_tool_args/get_tool_permission)继续工作
"""
from __future__ import annotations

import pytest


def test_tool_registry_exists() -> None:
    """TOOL_REGISTRY 必须存在且非空。"""
    from app.domain.agent.tools import TOOL_REGISTRY

    assert isinstance(TOOL_REGISTRY, dict)
    assert len(TOOL_REGISTRY) >= 5


def test_tool_registry_entry_has_all_fields() -> None:
    """每个 registry entry 必须含 schema/validator/permission/executor 字段。"""
    from app.domain.agent.tools import TOOL_REGISTRY

    for tool_name, entry in TOOL_REGISTRY.items():
        assert hasattr(entry, "schema"), f"{tool_name} missing schema"
        assert hasattr(entry, "validator"), f"{tool_name} missing validator"
        assert hasattr(entry, "permission"), f"{tool_name} missing permission"
        assert hasattr(entry, "executor"), f"{tool_name} missing executor"


def test_tool_registry_schema_is_function_dict() -> None:
    """registry 中的 schema 必须是 OpenAI function calling 格式(含 name + parameters)。"""
    from app.domain.agent.tools import TOOL_REGISTRY

    for tool_name, entry in TOOL_REGISTRY.items():
        schema = entry.schema
        # 可能是 wrapper {type:function, function:{...}} 或 inner
        if "function" in schema:
            inner = schema["function"]
        else:
            inner = schema
        assert inner.get("name") == tool_name
        assert "parameters" in inner


def test_tool_registry_validator_validates_args() -> None:
    """registry 中的 validator 必须能校验参数。"""
    from app.domain.agent.tools import TOOL_REGISTRY

    diagnose_entry = TOOL_REGISTRY["diagnose_brand"]
    validator = diagnose_entry.validator
    instance = validator(
        brand_name="小米",
        industry="消费电子",
        official_url="https://www.mi.com",
    )
    assert instance.brand_name == "小米"


def test_tool_registry_permission_has_required_fields() -> None:
    """permission 必须含 requires_confirmation/category/side_effect 字段。"""
    from app.domain.agent.tools import TOOL_REGISTRY

    for tool_name, entry in TOOL_REGISTRY.items():
        perm = entry.permission
        for field in ("requires_confirmation", "category", "side_effect"):
            assert field in perm, f"{tool_name} permission missing {field}"


def test_get_tool_schema_backward_compat() -> None:
    """get_tool_schema 旧 API 继续工作(返回 schema dict)。"""
    from app.domain.agent.tools import get_tool_schema

    schema = get_tool_schema("diagnose_brand")
    assert "name" in schema
    assert "parameters" in schema


def test_validate_tool_args_backward_compat() -> None:
    """validate_tool_args 旧 API 继续工作。"""
    from app.domain.agent.tools import validate_tool_args

    result = validate_tool_args(
        "diagnose_brand",
        {"brand_name": "小米", "industry": "消费电子", "official_url": "https://www.mi.com"},
    )
    assert result.brand_name == "小米"


def test_get_tool_permission_backward_compat() -> None:
    """get_tool_permission 旧 API 继续工作。"""
    from app.domain.agent.tools import get_tool_permission

    perm = get_tool_permission("diagnose_brand")
    assert perm["category"] == "read"


def test_tool_registry_list_tool_names() -> None:
    """registry 应有 list_tool_names() 便捷方法。"""
    from app.domain.agent.tools import list_tool_names

    names = list_tool_names()
    assert isinstance(names, list)
    assert "diagnose_brand" in names
    assert "search_knowledge" in names


def test_tool_registry_get_raises_on_unknown() -> None:
    """未知工具名应抛 ValueError。"""
    from app.domain.agent.tools import get_tool_entry

    with pytest.raises(ValueError):
        get_tool_entry("nonexistent_tool")


def test_tool_registry_consistent_with_separate_dicts() -> None:
    """registry 必须与旧 _TOOL_SCHEMAS / _VALIDATORS / _TOOL_PERMISSIONS 一致。"""
    from app.domain.agent import tools as t

    assert hasattr(t, "_TOOL_SCHEMAS")
    assert hasattr(t, "_VALIDATORS")
    assert hasattr(t, "_TOOL_PERMISSIONS")
    assert hasattr(t, "TOOL_REGISTRY")
    for name in t._TOOL_SCHEMAS:
        assert name in t.TOOL_REGISTRY
    for name in t._VALIDATORS:
        assert name in t.TOOL_REGISTRY
    for name in t._TOOL_PERMISSIONS:
        assert name in t.TOOL_REGISTRY