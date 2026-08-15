"""Settings.merge_runtime_overrides — JSON 覆盖合并到 Settings 实例。"""
from __future__ import annotations

import pytest
from cryptography.fernet import Fernet


def _install_test_store(monkeypatch, store):
    """把测试 store 注入到 get_default_model_config_store 单例位置。"""
    import app.core.config as cfg
    monkeypatch.setattr(cfg, "_DEFAULT_MODEL_CONFIG_STORE", store, raising=False)


@pytest.fixture(autouse=True)
def isolated_settings(monkeypatch, tmp_path):
    """重置 get_settings lru_cache，配置 ENCRYPTION_KEY + 临时 data/。"""
    from app.core.config import get_settings, reset_default_model_config_store
    monkeypatch.setenv("DEEPSEEK_API_KEY", "env-deepseek-key")
    monkeypatch.setenv("DEEPSEEK_MODEL", "env-deepseek-model")
    monkeypatch.setenv("OPENAI_API_KEY", "env-openai-key")
    monkeypatch.setenv("ENCRYPTION_KEY", Fernet.generate_key().decode())
    monkeypatch.setenv("GEO_ALLOW_MISSING_LLM_KEY", "1")  # 不强制要求 key
    monkeypatch.chdir(tmp_path)
    get_settings.cache_clear()
    reset_default_model_config_store()
    yield
    get_settings.cache_clear()
    reset_default_model_config_store()


def test_settings_uses_env_when_json_missing():
    from app.core.config import get_settings
    s = get_settings()
    assert s.deepseek_api_key == "env-deepseek-key"
    assert s.deepseek_model == "env-deepseek-model"


def _shared_key() -> str:
    """与 fixture monkeypatch 的 ENCRYPTION_KEY 保持一致。"""
    import os
    return os.environ["ENCRYPTION_KEY"]


def test_settings_json_overrides_env_per_field(tmp_path, monkeypatch):
    from app.core.config import get_settings
    from app.core.model_config_store import ModelConfigStore, ModelConfigSnapshot, ProviderOverride
    store = ModelConfigStore(path=tmp_path / "model_config.json", encryption_key=_shared_key())
    snap = ModelConfigSnapshot(
        providers={"deepseek": ProviderOverride(api_key_encrypted="", base_url="", model="json-deepseek-model")},
        tiers={}, fallback_chain=[], llm_providers=[], updated_at="2026-07-15T00:00:00+00:00"
    )
    store._cache = snap
    store._loaded = True
    _install_test_store(monkeypatch, store)
    get_settings.cache_clear()
    s = get_settings()
    assert s.deepseek_model == "json-deepseek-model"
    assert s.deepseek_api_key == "env-deepseek-key"  # 未覆盖 → 仍 .env


def test_settings_merges_all_provider_keys(tmp_path, monkeypatch):
    from app.core.config import get_settings
    from cryptography.fernet import Fernet
    from app.core.model_config_store import ModelConfigStore, ModelConfigSnapshot, ProviderOverride

    key = _shared_key()
    cipher = Fernet(key)
    store = ModelConfigStore(path=tmp_path / "model_config.json", encryption_key=key)
    encrypted = cipher.encrypt(b"new-openai-key").decode()
    snap = ModelConfigSnapshot(
        providers={
            "deepseek": ProviderOverride(api_key_encrypted="", base_url="", model="m1"),
            "openai": ProviderOverride(api_key_encrypted=encrypted, base_url="https://x", model="gpt-4"),
        },
        tiers={"cheap": "deepseek", "standard": "deepseek", "premium": "deepseek"},
        fallback_chain=["deepseek", "openai"],
        llm_providers=["deepseek", "openai"],
        updated_at="2026-07-15T00:00:00+00:00",
    )
    store._cache = snap
    store._loaded = True
    _install_test_store(monkeypatch, store)
    get_settings.cache_clear()
    s = get_settings()
    assert s.openai_api_key == "new-openai-key"
    assert s.deepseek_model == "m1"
    assert s.fallback_chain == "deepseek,openai"
    assert s.llm_providers == "deepseek,openai"


def test_settings_invalid_tier_falls_back_to_env(tmp_path, monkeypatch, caplog):
    from app.core.config import get_settings
    from app.core.model_config_store import ModelConfigStore, ModelConfigSnapshot, ProviderOverride
    store = ModelConfigStore(path=tmp_path / "model_config.json", encryption_key=_shared_key())
    snap = ModelConfigSnapshot(
        providers={},
        tiers={"cheap": "deepseek", "standard": "deepseek", "premium": "minimax"},
        fallback_chain=[], llm_providers=[], updated_at="2026-07-15T00:00:00+00:00"
    )
    store._cache = snap
    store._loaded = True
    _install_test_store(monkeypatch, store)
    get_settings.cache_clear()
    s = get_settings()
    # premium 在 .env 缺省 → "deepseek"（来自 Settings 默认值）
    assert s.model_tier_premium == "deepseek"


def test_settings_invalid_fallback_falls_back_to_env(tmp_path, monkeypatch):
    from app.core.config import get_settings
    from app.core.model_config_store import ModelConfigStore, ModelConfigSnapshot, ProviderOverride
    store = ModelConfigStore(path=tmp_path / "model_config.json", encryption_key=_shared_key())
    snap = ModelConfigSnapshot(
        providers={},
        tiers={}, fallback_chain=["deepseek", "minimax"], llm_providers=[],
        updated_at="2026-07-15T00:00:00+00:00"
    )
    store._cache = snap
    store._loaded = True
    _install_test_store(monkeypatch, store)
    get_settings.cache_clear()
    s = get_settings()
    # 整条 chain 引用未注册 → fall back 到 .env（"deepseek,kimi"）
    assert s.fallback_chain == "deepseek,kimi"


def test_settings_cache_cleared_after_store_update(tmp_path, monkeypatch):
    from app.core.config import get_settings
    from app.core.model_config_store import ModelConfigStore, ProviderPatch

    key = _shared_key()
    store = ModelConfigStore(path=tmp_path / "model_config.json", encryption_key=key)
    _install_test_store(monkeypatch, store)
    store.update(providers={"deepseek": ProviderPatch(name="deepseek", api_key="sk-new", model="new-m")})
    get_settings.cache_clear()
    s = get_settings()
    assert s.deepseek_api_key == "sk-new"
    assert s.deepseek_model == "new-m"


def test_settings_merges_each_call_after_clear(tmp_path, monkeypatch):
    from app.core.config import get_settings
    from app.core.model_config_store import ModelConfigStore, ProviderPatch

    key = _shared_key()
    store = ModelConfigStore(path=tmp_path / "model_config.json", encryption_key=key)
    _install_test_store(monkeypatch, store)
    store.update(providers={"deepseek": ProviderPatch(name="deepseek", model="m-1")})
    get_settings.cache_clear()
    assert get_settings().deepseek_model == "m-1"
    store.update(providers={"deepseek": ProviderPatch(name="deepseek", model="m-2")})
    get_settings.cache_clear()
    assert get_settings().deepseek_model == "m-2"