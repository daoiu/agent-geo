"""v0.6+ P1#20（Task 21）：显式 Providers 抽象。

集中管理 LLM provider 配置：
- API key 解析（从 Settings.*_API_KEY 读）
- Base URL / model 名
- 单价（pricing_per_1k 用于 Task 24 cost 计算）
- Telemetry 接入点（langfuse / sentry 在 main.py 启动时已 init,此处引用）

替代散落在 llm_client.py 的 if/elif,便于:
1. 加 provider 只改 PROVIDERS_META + Settings 加 *_API_KEY 字段
2. cost 计算统一入口（compute_cost）
3. 测试可注入 mock provider 配置

注：auth 实际由 OpenAI SDK 处理（api_key 透传），这里只做配置解析。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

from app.core.config import Settings, get_settings


@dataclass(frozen=True)
class LLMProvider:
    """LLM provider 配置聚合。

    不可变(frozen=True),避免运行时被改。
    """

    name: str
    api_key: str
    base_url: str
    model: str
    pricing_per_1k: dict[str, float] = field(default_factory=dict)


# v0.6+ P1#20 集中 provider 元数据。
# 字段：env_key（Settings 字段名）/ base_url / model / pricing_per_1k
# 加新 provider 时只需在这里加一条 + Settings 加 api_key 字段。
PROVIDERS_META: dict[str, dict[str, Any]] = {
    "deepseek": {
        "env_key": "deepseek_api_key",
        "base_url": "https://api.deepseek.com/v1",
        "model": "deepseek-chat",
        "pricing_per_1k": {"prompt": 0.00027, "completion": 0.0011},
    },
    "kimi": {
        "env_key": "kimi_api_key",
        "base_url": "https://api.moonshot.cn/v1",
        "model": "moonshot-v1-8k",
        "pricing_per_1k": {"prompt": 0.002, "completion": 0.002},
    },
    "openai": {
        "env_key": "openai_api_key",
        "base_url": "https://api.openai.com/v1",
        "model": "gpt-4o-mini",
        "pricing_per_1k": {"prompt": 0.00015, "completion": 0.0006},
    },
}


def resolve_providers(settings: Settings | None = None) -> list[LLMProvider]:
    """从 Settings 解析 LLM providers 列表。

    按 settings.llm_providers（逗号分隔）顺序，过滤掉没配 API key 的 provider。
    返回的 provider 都有非空 api_key。
    """
    s = settings if settings is not None else get_settings()
    enabled_names = [n.strip() for n in s.llm_providers.split(",") if n.strip()]

    providers: list[LLMProvider] = []
    for name in enabled_names:
        meta = PROVIDERS_META.get(name)
        if not meta:
            continue
        api_key = getattr(s, meta["env_key"], "") or ""
        if not api_key:
            # 跳过未配 api_key 的 provider
            continue
        providers.append(LLMProvider(
            name=name,
            api_key=api_key,
            base_url=meta["base_url"],
            model=meta["model"],
            pricing_per_1k=meta.get("pricing_per_1k", {}),
        ))
    return providers


def compute_cost(
    provider: LLMProvider,
    prompt_tokens: int,
    completion_tokens: int,
) -> Decimal:
    """基于 provider.pricing_per_1k 计算 USD 成本。

    用 Decimal 避免 float 精度损失。pricing 缺失时返回 0。
    """
    pricing = provider.pricing_per_1k or {}
    prompt_rate = Decimal(str(pricing.get("prompt", 0)))
    completion_rate = Decimal(str(pricing.get("completion", 0)))

    cost = (
        Decimal(prompt_tokens) * prompt_rate / Decimal(1000)
        + Decimal(completion_tokens) * completion_rate / Decimal(1000)
    )
    return cost.quantize(Decimal("0.0000001"))  # 7 位小数精度