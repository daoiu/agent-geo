"""自适应模型选择(P2#50 / Task 36)。

三档模型:
- cheap: 轻量任务(关键词提取/分类/简短对话) - 优先选最快最便宜的
- standard: 默认任务(常规对话/工具调用) - 平衡质量与成本
- premium: 复杂任务(多步推理/创意生成/关键决策) - 优先选最强模型

复杂度分类(classify_complexity)考虑:
- query 长度
- 工具调用数量(tool_count)
- 显式 hint(hint="complex" 强制升级)

降级策略(适配 Settings 中 provider 缺 key 的场景):
- 选择 cheap 时若 cheap provider 无 key,降级到 standard
- 选择 premium 时若 premium provider 无 key,降级到 standard
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from enum import Enum

from .config import Settings, get_settings


class TaskComplexity(str, Enum):
    SIMPLE = "simple"
    STANDARD = "standard"
    COMPLEX = "complex"


@dataclass(frozen=True)
class ModelSelection:
    """模型选择结果。"""

    provider: str
    model: str
    tier: str  # cheap / standard / premium

    def __repr__(self) -> str:
        return f"ModelSelection({self.provider}/{self.model} tier={self.tier})"


# Provider → 默认模型映射(供默认 cheap/standard/premium 选择)
_PROVIDER_DEFAULT_MODELS: dict[str, str] = {
    "deepseek": "deepseek-chat",
    "kimi": "moonshot-v1-8k",
    "openai": "gpt-4o-mini",
    "minimax": "MiniMax-M2.7",
}


def _provider_has_key(provider: str) -> bool:
    """检查 provider 是否有 API key 配置。"""
    env_map = {
        "deepseek": "DEEPSEEK_API_KEY",
        "kimi": "KIMI_API_KEY",
        "openai": "OPENAI_API_KEY",
        "minimax": "MINIMAX_API_KEY",
    }
    env_name = env_map.get(provider, f"{provider.upper()}_API_KEY")
    return bool(os.environ.get(env_name))


def _resolve_model(provider: str, settings: Settings) -> str:
    """根据 provider 找到对应的默认模型名。"""
    if provider == "deepseek":
        return settings.deepseek_model
    if provider == "kimi":
        return settings.kimi_model
    # 未知 provider 用 PROVIDER_DEFAULT_MODELS 默认值
    return _PROVIDER_DEFAULT_MODELS.get(provider, "gpt-4o-mini")


def classify_complexity(
    query: str,
    tool_count: int = 0,
    hint: str | None = None,
) -> str:
    """根据 query 长度 + 工具调用数量 + 显式 hint 决定复杂度。

    返回 "simple" / "standard" / "complex"。
    """
    if hint in ("simple", "standard", "complex"):
        return hint

    # 工具调用数量权重最高
    if tool_count >= 4:
        return "complex"
    if tool_count >= 2:
        return "standard"

    # query 长度权重
    n = len(query)
    if n >= 800:
        return "complex"
    if n >= 200:
        return "standard"
    return "simple"


def select_model(
    complexity: TaskComplexity | str,
    settings: Settings | None = None,
) -> ModelSelection:
    """根据复杂度选择模型。带降级(若 tier provider 无 key)。

    复杂度 → 首选 tier → 若无 key 降级。
    """
    if isinstance(complexity, str):
        complexity = TaskComplexity(complexity)
    settings = settings or get_settings()

    tier_to_provider = {
        TaskComplexity.SIMPLE: settings.model_tier_cheap,
        TaskComplexity.STANDARD: settings.model_tier_standard,
        TaskComplexity.COMPLEX: settings.model_tier_premium,
    }

    # 降级顺序:目标 tier → standard → cheap → premium(总有一个有效)
    target_tier_map = {
        TaskComplexity.SIMPLE: ["cheap", "standard", "premium"],
        TaskComplexity.STANDARD: ["standard", "cheap", "premium"],
        TaskComplexity.COMPLEX: ["premium", "standard", "cheap"],
    }
    tier_to_attr = {
        "cheap": settings.model_tier_cheap,
        "standard": settings.model_tier_standard,
        "premium": settings.model_tier_premium,
    }

    for tier in target_tier_map[complexity]:
        provider = tier_to_attr[tier]
        if _provider_has_key(provider):
            model = _resolve_model(provider, settings)
            return ModelSelection(provider=provider, model=model, tier=tier)

    # 所有 tier 都无 key(测试场景),返回第一个 tier 不抛
    fallback_tier = target_tier_map[complexity][0]
    fallback_provider = tier_to_attr[fallback_tier]
    return ModelSelection(
        provider=fallback_provider,
        model=_resolve_model(fallback_provider, settings),
        tier=fallback_tier,
    )


__all__ = [
    "ModelSelection",
    "TaskComplexity",
    "classify_complexity",
    "select_model",
]