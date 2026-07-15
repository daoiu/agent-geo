"""API integration tests for /api/settings/models (Task 41)."""
from __future__ import annotations

import sys
import types

# Stub langfuse — 本地可能未安装，且本测试不真正调用 LLM
if "langfuse" not in sys.modules:
    _stub = types.ModuleType("langfuse")
    _stub.Langfuse = type("Langfuse", (), {})
    sys.modules["langfuse"] = _stub

import pytest
from cryptography.fernet import Fernet


def _patch_settings(monkeypatch, tmp_path):
    """Helper: set encryption_key + data dir, return (client, store)."""
    from app.core.config import get_settings, reset_default_model_config_store
    monkeypatch.setenv("ENCRYPTION_KEY", Fernet.generate_key().decode())
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-deepseek-key")
    monkeypatch.setenv("OPENAI_API_KEY", "test-openai-key")
    monkeypatch.setenv("GEO_ALLOW_MISSING_LLM_KEY", "1")
    monkeypatch.chdir(tmp_path)
    get_settings.cache_clear()
    reset_default_model_config_store()


@pytest.fixture(autouse=True)
def reset_between_tests(monkeypatch, tmp_path):
    _patch_settings(monkeypatch, tmp_path)
    yield
    from app.core.config import get_settings, reset_default_model_config_store
    get_settings.cache_clear()
    reset_default_model_config_store()


def test_get_returns_providers_from_settings(client):
    r = client.get("/api/settings/models")
    assert r.status_code == 200
    data = r.json()
    names = [p["name"] for p in data["providers"]]
    assert "deepseek" in names
    assert "kimi" in names
    assert "openai" in names


def test_get_masks_api_key_when_set(client):
    r = client.get("/api/settings/models")
    data = r.json()
    deepseek = next(p for p in data["providers"] if p["name"] == "deepseek")
    assert deepseek["api_key_set"] is True
    assert deepseek["api_key_masked"].startswith("tes")
    assert "***" in deepseek["api_key_masked"]


def test_get_omits_mask_when_unset(client):
    r = client.get("/api/settings/models")
    data = r.json()
    kimi = next(p for p in data["providers"] if p["name"] == "kimi")
    assert kimi["api_key_set"] is False
    assert kimi["api_key_masked"] == ""


def test_get_reports_source_json_when_override_exists(client):
    # 写入一个 provider 到 store
    client.patch("/api/settings/models", json={
        "providers": [{"name": "deepseek", "model": "deepseek-v2"}]
    })
    r = client.get("/api/settings/models")
    assert r.json()["source"] == "json"


def test_get_reports_source_env_when_no_override(client):
    r = client.get("/api/settings/models")
    assert r.json()["source"] == "env"


def test_patch_updates_store_and_clears_cache(client):
    r = client.patch("/api/settings/models", json={
        "providers": [{"name": "deepseek", "model": "deepseek-v3"}]
    })
    assert r.status_code == 200
    from app.core.config import get_settings
    assert get_settings().deepseek_model == "deepseek-v3"


def test_patch_rejects_unknown_provider_in_tier(client):
    r = client.patch("/api/settings/models", json={
        "tiers": {"cheap": "deepseek", "standard": "deepseek", "premium": "minimax"}
    })
    assert r.status_code == 422
    body = r.json()
    # FastAPI default validation OR our custom — check code presence
    assert "minimax" in str(body) or "unknown_provider" in str(body)


def test_patch_rejects_invalid_base_url(client):
    r = client.patch("/api/settings/models", json={
        "providers": [{"name": "deepseek", "base_url": "not-a-url"}]
    })
    assert r.status_code == 422


def test_patch_rejects_empty_model(client):
    r = client.patch("/api/settings/models", json={
        "providers": [{"name": "deepseek", "model": ""}]
    })
    assert r.status_code == 422


def test_patch_rejects_when_encryption_key_missing_and_payload_has_key(client, monkeypatch, tmp_path):
    monkeypatch.setenv("ENCRYPTION_KEY", "")
    monkeypatch.setenv("GEO_ALLOW_MISSING_LLM_KEY", "1")
    monkeypatch.chdir(tmp_path)
    from app.core.config import get_settings, reset_default_model_config_store
    get_settings.cache_clear()
    reset_default_model_config_store()
    r = client.patch("/api/settings/models", json={
        "providers": [{"name": "deepseek", "api_key": "sk-new"}]
    })
    assert r.status_code == 422
    assert "encryption_key_missing" in str(r.json())


def test_patch_allows_non_key_fields_when_encryption_key_missing(client, monkeypatch, tmp_path):
    monkeypatch.setenv("ENCRYPTION_KEY", "")
    monkeypatch.setenv("GEO_ALLOW_MISSING_LLM_KEY", "1")
    monkeypatch.chdir(tmp_path)
    from app.core.config import get_settings, reset_default_model_config_store
    get_settings.cache_clear()
    reset_default_model_config_store()
    r = client.patch("/api/settings/models", json={
        "providers": [{"name": "deepseek", "model": "new-m"}]
    })
    assert r.status_code == 200


def test_patch_empty_api_key_does_not_clear_existing(client):
    # First set a key
    client.patch("/api/settings/models", json={
        "providers": [{"name": "deepseek", "api_key": "sk-original"}]
    })
    # Then send empty
    client.patch("/api/settings/models", json={
        "providers": [{"name": "deepseek", "api_key": ""}]
    })
    from app.core.config import get_settings
    assert get_settings().deepseek_api_key == "sk-original"


def test_patch_missing_api_key_does_not_clear_existing(client):
    client.patch("/api/settings/models", json={
        "providers": [{"name": "deepseek", "api_key": "sk-original"}]
    })
    client.patch("/api/settings/models", json={
        "providers": [{"name": "deepseek", "model": "deepseek-v2"}]
    })
    from app.core.config import get_settings
    assert get_settings().deepseek_api_key == "sk-original"


def test_reset_clears_overrides_and_falls_back_to_env(client):
    client.patch("/api/settings/models", json={
        "providers": [{"name": "deepseek", "model": "deepseek-v3"}]
    })
    from app.core.config import get_settings
    assert get_settings().deepseek_model == "deepseek-v3"
    r = client.post("/api/settings/models/reset")
    assert r.status_code == 200
    # fallback 到 .env baseline（fixture 设的 DEEPSEEK_MODEL 是默认 "deepseek-chat"）
    assert get_settings().deepseek_model == "deepseek-chat"
    assert r.json()["source"] == "env"


def test_patch_returns_updated_dto(client):
    r = client.patch("/api/settings/models", json={
        "providers": [{"name": "deepseek", "model": "deepseek-v3"}]
    })
    body = r.json()
    deepseek = next(p for p in body["providers"] if p["name"] == "deepseek")
    assert deepseek["model"] == "deepseek-v3"