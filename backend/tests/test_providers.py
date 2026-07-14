"""验证显式 Providers 抽象（P1#20 / Task 21）。

行为契约：
- LLMProvider dataclass 持有 name/api_key/base_url/model/pricing
- resolve_providers() 从 Settings 读 LLM_PROVIDERS + *_API_KEY 构造 providers 列表
- 已知 provider 列表：deepseek / kimi / openai
- compute_cost(provider, prompt_tokens, completion_tokens) 基于 pricing 计算 USD 成本
- PROVIDERS_META 集中表（auth / telemetry 入口）
"""
from __future__ import annotations

from decimal import Decimal

import pytest


def test_llm_provider_dataclass_fields() -> None:
    """LLMProvider 必须有 name / api_key / base_url / model / pricing_per_1k。"""
    from app.core.providers import LLMProvider

    p = LLMProvider(
        name="deepseek",
        api_key="sk-test",
        base_url="https://api.deepseek.com/v1",
        model="deepseek-chat",
        pricing_per_1k={"prompt": 0.001, "completion": 0.002},
    )
    assert p.name == "deepseek"
    assert p.api_key == "sk-test"
    assert p.pricing_per_1k["prompt"] == 0.001


def test_resolve_providers_returns_list(monkeypatch) -> None:
    """resolve_providers 应返回 LLMProvider 列表（按 Settings.llm_providers 顺序）。"""
    from app.core.providers import resolve_providers
    from app.core.config import get_settings

    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-deepseek-test")
    monkeypatch.setenv("LLM_PROVIDERS", "deepseek")  # 显式覆盖 .env 默认
    get_settings.cache_clear()  # type: ignore[attr-defined]

    providers = resolve_providers()
    assert isinstance(providers, list)
    # 应至少有一个 deepseek
    names = [p.name for p in providers]
    assert "deepseek" in names


def test_resolve_providers_filters_unconfigured_keys(monkeypatch) -> None:
    """resolve_providers 应跳过没配 API key 的 provider（避免空 key 启动）。"""
    from app.core.providers import resolve_providers
    from app.core.config import get_settings

    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-deepseek-test")
    monkeypatch.setenv("KIMI_API_KEY", "")  # 显式清空 kimi
    monkeypatch.setenv("LLM_PROVIDERS", "deepseek,kimi")
    get_settings.cache_clear()  # type: ignore[attr-defined]

    providers = resolve_providers()
    for p in providers:
        # 所有返回的 provider 都必须有非空 api_key
        assert p.api_key, f"{p.name} 缺少 api_key,不应在返回列表"
    # 至少 deepseek 应被返回
    names = [p.name for p in providers]
    assert "deepseek" in names
    # kimi 因为没 api_key,不应在返回列表
    assert "kimi" not in names


def test_compute_cost_basic() -> None:
    """compute_cost(provider, prompt_tokens, completion_tokens) 应基于 pricing 计算。"""
    from app.core.providers import LLMProvider, compute_cost

    p = LLMProvider(
        name="test",
        api_key="x",
        base_url="x",
        model="x",
        pricing_per_1k={"prompt": 0.001, "completion": 0.002},
    )
    # 1000 prompt + 500 completion = 0.001 + 0.001 = 0.002
    cost = compute_cost(p, prompt_tokens=1000, completion_tokens=500)
    assert cost == Decimal("0.002")


def test_compute_cost_zero_tokens() -> None:
    """compute_cost(0, 0) → 0（不抛异常）。"""
    from app.core.providers import LLMProvider, compute_cost

    p = LLMProvider(
        name="t", api_key="x", base_url="x", model="x",
        pricing_per_1k={"prompt": 0.001, "completion": 0.002},
    )
    assert compute_cost(p, 0, 0) == Decimal("0")


def test_compute_cost_missing_pricing_returns_zero() -> None:
    """provider 没配 pricing 时 compute_cost 返回 0（不抛）。"""
    from app.core.providers import LLMProvider, compute_cost

    p = LLMProvider(
        name="t", api_key="x", base_url="x", model="x",
        pricing_per_1k={},
    )
    assert compute_cost(p, 1000, 500) == Decimal("0")


def test_compute_cost_chinese_pricing_decimals() -> None:
    """小数精度正确（用 Decimal 避免 float 误差）。"""
    from app.core.providers import LLMProvider, compute_cost

    p = LLMProvider(
        name="t", api_key="x", base_url="x", model="x",
        pricing_per_1k={"prompt": 0.0001, "completion": 0.0002},
    )
    # 1234 prompt + 567 completion
    # = 1234/1000 * 0.0001 + 567/1000 * 0.0002
    # = 0.0001234 + 0.0001134
    # = 0.0002368
    cost = compute_cost(p, 1234, 567)
    assert cost == Decimal("0.0002368")


def test_provider_meta_known_providers() -> None:
    """PROVIDERS_META 必须包含 deepseek / kimi / openai 三个 provider。"""
    from app.core.providers import PROVIDERS_META

    assert "deepseek" in PROVIDERS_META
    assert "kimi" in PROVIDERS_META
    assert "openai" in PROVIDERS_META


def test_provider_meta_has_pricing() -> None:
    """PROVIDERS_META 每条目必须有 pricing_per_1k。"""
    from app.core.providers import PROVIDERS_META

    for name, meta in PROVIDERS_META.items():
        assert "pricing_per_1k" in meta, f"{name} 缺 pricing_per_1k"
        p = meta["pricing_per_1k"]
        assert "prompt" in p and "completion" in p, (
            f"{name} pricing 缺 prompt/completion"
        )