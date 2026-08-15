"""P1#35（Task 36）: 自适应模型选择测试。

目标:
- Settings 加 cheap/standard/premium 三档模型配置
- select_model(complexity) 根据复杂度返回对应 provider+model
- 默认 cheap 用于轻量任务,premium 用于关键决策
"""
from __future__ import annotations

import os
from unittest.mock import patch

import pytest


def test_settings_has_model_tier_config():
    """Settings 必须包含 cheap/standard/premium 三档模型配置。"""
    with patch.dict(os.environ, {"GEO_ALLOW_MISSING_LLM_KEY": "1"}, clear=False):
        from app.core.config import Settings

        s = Settings()
        # 三档必须存在
        assert hasattr(s, "model_tier_cheap"), "missing model_tier_cheap"
        assert hasattr(s, "model_tier_standard"), "missing model_tier_standard"
        assert hasattr(s, "model_tier_premium"), "missing model_tier_premium"
        # 都有非空默认值
        assert s.model_tier_cheap, "model_tier_cheap must have default"
        assert s.model_tier_standard, "model_tier_standard must have default"
        assert s.model_tier_premium, "model_tier_premium must have default"


def test_select_model_cheap_for_simple_tasks():
    """简单任务(分类/关键词提取)应使用 cheap 模型。"""
    from app.core.adaptive_model import TaskComplexity, select_model

    selection = select_model(TaskComplexity.SIMPLE)
    assert selection.tier == "cheap"
    assert selection.provider
    assert selection.model


def test_select_model_premium_for_complex_tasks():
    """复杂任务(多步推理/创意生成)应使用 premium 模型。"""
    from app.core.adaptive_model import TaskComplexity, select_model

    selection = select_model(TaskComplexity.COMPLEX)
    assert selection.tier == "premium"


def test_select_model_standard_for_default_tasks():
    """默认任务(对话/工具调用)应使用 standard 模型。"""
    from app.core.adaptive_model import TaskComplexity, select_model

    selection = select_model(TaskComplexity.STANDARD)
    assert selection.tier == "standard"


def test_complexity_from_query_length():
    """根据 query 长度自动分级(SHORT→SIMPLE / MEDIUM→STANDARD / LONG→COMPLEX)。"""
    from app.core.adaptive_model import classify_complexity

    assert classify_complexity("hi") == "simple"
    assert classify_complexity("a" * 50) == "simple"
    assert classify_complexity("a" * 300) == "standard"
    assert classify_complexity("a" * 1500) == "complex"


def test_complexity_from_tool_call_count():
    """多步工具调用 → 升级到 standard/complex。"""
    from app.core.adaptive_model import classify_complexity

    # 简单查询 + 0 工具 → simple
    assert classify_complexity("hi", tool_count=0) == "simple"
    # 简单查询 + 2 工具 → standard(推断需要协调)
    assert classify_complexity("hi", tool_count=2) == "standard"
    # 简单查询 + 5 工具 → complex(协调成本高)
    assert classify_complexity("hi", tool_count=5) == "complex"


def test_select_model_respects_settings_override():
    """通过 env var 覆盖 tier 配置应生效。"""
    with patch.dict(os.environ, {
        "GEO_ALLOW_MISSING_LLM_KEY": "1",
        "MODEL_TIER_CHEAP": "kimi",
        "KIMI_API_KEY": "test-key",  # 满足 model_validator
    }):
        from app.core.config import Settings
        from app.core.adaptive_model import TaskComplexity, select_model

        s = Settings()
        assert s.model_tier_cheap == "kimi"
        selection = select_model(TaskComplexity.SIMPLE, settings=s)
        assert selection.provider == "kimi"


def test_adaptive_model_dataclass():
    """ModelSelection 必须是 dataclass 含 provider/model/tier 字段。"""
    from app.core.adaptive_model import ModelSelection

    sel = ModelSelection(provider="openai", model="gpt-4", tier="premium")
    assert sel.provider == "openai"
    assert sel.model == "gpt-4"
    assert sel.tier == "premium"


def test_select_model_falls_back_when_tier_provider_missing(monkeypatch):
    """tier 指定的 provider 缺 key 时,应降级到下一个可用 tier。"""
    # 清空所有可能的 provider key,确保 _provider_has_key 只看我们设置的
    for key in list(os.environ.keys()):
        if key.endswith("_API_KEY") and key not in ("ANTHROPIC_API_KEY",):
            monkeypatch.delenv(key, raising=False)
    # 只保留 deepseek 作为可用降级目标
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-deepseek-key")
    monkeypatch.setenv("GEO_ALLOW_MISSING_LLM_KEY", "1")
    monkeypatch.setenv("MODEL_TIER_CHEAP", "kimi")  # kimi 无 key,应降级
    monkeypatch.setenv("MODEL_TIER_STANDARD", "deepseek")  # 标准档有 key

    from app.core.config import Settings
    from app.core.adaptive_model import TaskComplexity, select_model

    s = Settings()
    assert s.model_tier_cheap == "kimi"
    assert s.model_tier_standard == "deepseek"
    selection = select_model(TaskComplexity.SIMPLE, settings=s)
    # 应降级到 standard (deepseek),不应返回 kimi
    assert selection.provider == "deepseek"
    assert selection.tier == "standard"