"""v0.7+ 设置 — 模型配置 API (Task 41)。"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import AnyHttpUrl, BaseModel, field_validator

from app.core.config import get_default_model_config_store, get_settings
from app.core.model_config_store import ProviderPatch
from app.core.providers import PROVIDERS_META

router = APIRouter(prefix="/settings/models", tags=["settings"])


# === Request / Response DTOs ===

class ProviderUpdate(BaseModel):
    name: str
    api_key: str | None = None
    base_url: AnyHttpUrl | None = None
    model: str | None = None

    @field_validator("name")
    @classmethod
    def _name_known(cls, v: str) -> str:
        if v not in PROVIDERS_META:
            raise ValueError(f"unknown provider: {v}")
        return v

    @field_validator("model")
    @classmethod
    def _model_not_empty(cls, v: str | None) -> str | None:
        if v is not None and not v.strip():
            raise ValueError("model must not be empty")
        return v


class TiersUpdate(BaseModel):
    cheap: str | None = None
    standard: str | None = None
    premium: str | None = None


class ModelConfigUpdate(BaseModel):
    providers: list[ProviderUpdate] | None = None
    tiers: TiersUpdate | None = None
    fallback_chain: list[str] | None = None
    llm_providers: list[str] | None = None


class ProviderDTO(BaseModel):
    name: str
    base_url: str
    model: str
    api_key_set: bool
    api_key_masked: str


class ModelConfigDTO(BaseModel):
    providers: list[ProviderDTO]
    tiers: dict[str, str]
    fallback_chain: list[str]
    llm_providers: list[str]
    source: str
    updated_at: str


# === Helpers ===

def _mask_key(value: str) -> str:
    """API key 掩码：value[:3] + "***" + value[-3:]（len>=8），否则 "***"；空字符串返回 ""。"""
    if not value:
        return ""
    if len(value) < 8:
        return "***"
    return value[:3] + "***" + value[-3:]


def _split_list(value: str) -> list[str]:
    return [p.strip() for p in (value or "").split(",") if p.strip()]


def _build_dto() -> ModelConfigDTO:
    """从当前 Settings + store 状态组装 DTO（前端 GET 用）。"""
    settings = get_settings()
    store = get_default_model_config_store()
    snap = store.load_snapshot()

    providers_dto: list[ProviderDTO] = []
    for name, meta in PROVIDERS_META.items():
        api_key = getattr(settings, f"{name}_api_key", "") or ""
        base_url = getattr(settings, f"{name}_base_url", "") or meta["base_url"]
        model = getattr(settings, f"{name}_model", "") or meta["model"]
        api_key_set = bool(api_key)
        providers_dto.append(ProviderDTO(
            name=name,
            base_url=base_url,
            model=model,
            api_key_set=api_key_set,
            api_key_masked=_mask_key(api_key) if api_key_set else "",
        ))

    has_overrides = bool(snap and (
        snap.providers or snap.tiers or snap.fallback_chain or snap.llm_providers
    ))

    return ModelConfigDTO(
        providers=providers_dto,
        tiers={
            "cheap": settings.model_tier_cheap,
            "standard": settings.model_tier_standard,
            "premium": settings.model_tier_premium,
        },
        fallback_chain=_split_list(settings.fallback_chain),
        llm_providers=_split_list(settings.llm_providers),
        source="json" if has_overrides else "env",
        updated_at=snap.updated_at if snap else "",
    )


# === Endpoints ===

@router.get("", response_model=ModelConfigDTO)
async def get_model_config() -> ModelConfigDTO:
    return _build_dto()


@router.patch("", response_model=ModelConfigDTO)
async def update_model_config(body: ModelConfigUpdate) -> ModelConfigDTO:
    # 1. 校验 tier 引用
    if body.tiers:
        for tier_key, provider_name in body.tiers.model_dump(exclude_none=True).items():
            if provider_name not in PROVIDERS_META:
                raise HTTPException(
                    status_code=422,
                    detail={
                        "code": "unknown_provider",
                        "field": f"tiers.{tier_key}",
                        "message": f"unknown provider: {provider_name}",
                    },
                )
    # 2. 校验 fallback_chain
    if body.fallback_chain:
        for p in body.fallback_chain:
            if p not in PROVIDERS_META:
                raise HTTPException(
                    status_code=422,
                    detail={
                        "code": "unknown_provider",
                        "field": "fallback_chain",
                        "message": f"unknown provider: {p}",
                    },
                )
    # 3. 校验 llm_providers
    if body.llm_providers:
        for p in body.llm_providers:
            if p not in PROVIDERS_META:
                raise HTTPException(
                    status_code=422,
                    detail={
                        "code": "unknown_provider",
                        "field": "llm_providers",
                        "message": f"unknown provider: {p}",
                    },
                )

    settings = get_settings()
    encryption_key = settings.encryption_key or ""

    # 4. ENCRYPTION_KEY 检查（仅当 payload 含非空 api_key）
    has_non_empty_api_key = False
    if body.providers:
        for p in body.providers:
            if p.api_key and p.api_key.strip():
                has_non_empty_api_key = True
                break
    if has_non_empty_api_key and not encryption_key:
        raise HTTPException(
            status_code=422,
            detail={
                "code": "encryption_key_missing",
                "message": "ENCRYPTION_KEY not set; cannot save API key",
            },
        )

    # 5. 调 store.update
    store = get_default_model_config_store()
    providers_patches: dict[str, ProviderPatch] = {}
    if body.providers:
        for p in body.providers:
            api_key_value = p.api_key if (p.api_key and p.api_key.strip()) else None
            providers_patches[p.name] = ProviderPatch(
                name=p.name,
                api_key=api_key_value,
                base_url=str(p.base_url) if p.base_url else None,
                model=p.model,
            )
    tiers_dict = body.tiers.model_dump(exclude_none=True) if body.tiers else None

    store.update(
        providers=providers_patches or None,
        tiers=tiers_dict,
        fallback_chain=body.fallback_chain,
        llm_providers=body.llm_providers,
    )

    # 6. 失效 cache + 重新构造
    get_settings.cache_clear()
    return _build_dto()


@router.post("/reset", response_model=ModelConfigDTO)
async def reset_model_config() -> ModelConfigDTO:
    store = get_default_model_config_store()
    store.delete_file()
    get_settings.cache_clear()
    return _build_dto()