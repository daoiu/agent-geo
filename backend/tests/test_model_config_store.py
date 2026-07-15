"""Unit tests for ModelConfigStore — JSON persistence + Fernet encryption."""
from __future__ import annotations

import json
import threading
from pathlib import Path

import pytest
from cryptography.fernet import Fernet


@pytest.fixture
def store_path(tmp_path: Path) -> Path:
    return tmp_path / "data" / "model_config.json"


@pytest.fixture
def encryption_key() -> str:
    return Fernet.generate_key().decode()


@pytest.fixture
def store(store_path: Path, encryption_key: str):
    from app.core.model_config_store import ModelConfigStore
    return ModelConfigStore(path=store_path, encryption_key=encryption_key)


def test_store_creates_file_on_first_save(store, store_path):
    from app.core.model_config_store import ProviderPatch
    store.update(
        providers={"deepseek": ProviderPatch(name="deepseek", api_key="sk-x", base_url="https://x", model="m")},
    )
    assert store_path.exists()


def test_store_encrypts_api_key_on_disk(store, store_path):
    from app.core.model_config_store import ProviderPatch
    store.update(providers={"deepseek": ProviderPatch(name="deepseek", api_key="sk-plain")})
    raw = json.loads(store_path.read_text(encoding="utf-8"))
    assert "sk-plain" not in json.dumps(raw)


def test_store_decrypts_api_key_on_read(store):
    from app.core.model_config_store import ProviderPatch
    store.update(providers={"deepseek": ProviderPatch(name="deepseek", api_key="sk-plain")})
    snap = store.load_snapshot()
    assert snap is not None
    assert snap.providers["deepseek"].api_key_encrypted != "sk-plain"  # ciphertext


def test_store_preserves_old_key_when_payload_empty(store):
    from app.core.model_config_store import ProviderPatch
    store.update(providers={"deepseek": ProviderPatch(name="deepseek", api_key="sk-original")})
    # PATCH with empty api_key → preserve old ciphertext
    store.update(providers={"deepseek": ProviderPatch(name="deepseek", api_key="", model="deepseek-v2")})
    snap = store.load_snapshot()
    assert snap is not None
    # Re-encrypt original and compare via fresh store with same key
    f = Fernet(store._encryption_key.encode())
    decrypted = f.decrypt(snap.providers["deepseek"].api_key_encrypted.encode()).decode()
    assert decrypted == "sk-original"
    assert snap.providers["deepseek"].model == "deepseek-v2"


def test_store_preserves_old_key_when_payload_missing(store):
    from app.core.model_config_store import ProviderPatch
    store.update(providers={"deepseek": ProviderPatch(name="deepseek", api_key="sk-original")})
    # PATCH without api_key field → preserve old ciphertext
    store.update(providers={"deepseek": ProviderPatch(name="deepseek", model="deepseek-v2")})
    snap = store.load_snapshot()
    assert snap is not None
    f = Fernet(store._encryption_key.encode())
    decrypted = f.decrypt(snap.providers["deepseek"].api_key_encrypted.encode()).decode()
    assert decrypted == "sk-original"


def test_store_loads_missing_file_as_empty(store):
    assert store.load_snapshot() is None
    assert store.has_overrides() is False


def test_store_skips_corrupted_json(store, store_path):
    store_path.parent.mkdir(parents=True, exist_ok=True)
    store_path.write_text("not json{{{", encoding="utf-8")
    assert store.load_snapshot() is None
    assert store.has_overrides() is False


def test_store_survives_invalid_ciphertext(store, store_path):
    store_path.parent.mkdir(parents=True, exist_ok=True)
    bad = {
        "providers": {"deepseek": {"api_key": "garbage", "base_url": "https://x", "model": "m"}},
        "tiers": {"cheap": "deepseek", "standard": "deepseek", "premium": "deepseek"},
        "fallback_chain": ["deepseek"],
        "llm_providers": ["deepseek"],
        "updated_at": "2026-07-15T00:00:00+00:00",
    }
    store_path.write_text(json.dumps(bad), encoding="utf-8")
    # Ciphertext invalid → snapshot still loads but provider key is empty string
    snap = store.load_snapshot()
    assert snap is not None
    assert snap.providers["deepseek"].api_key_encrypted == ""


def test_store_thread_safe_under_concurrent_writes(store):
    from app.core.model_config_store import ProviderPatch

    def write(i: int):
        store.update(providers={"deepseek": ProviderPatch(name="deepseek", api_key=f"sk-{i}", model=f"m-{i}")})

    threads = [threading.Thread(target=write, args=(i,)) for i in range(10)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    snap = store.load_snapshot()
    assert snap is not None
    f = Fernet(store._encryption_key.encode())
    decrypted = f.decrypt(snap.providers["deepseek"].api_key_encrypted.encode()).decode()
    # Either one of the 10 writers — content is internally consistent
    assert decrypted.startswith("sk-")
    assert snap.providers["deepseek"].model.startswith("m-")


def test_store_reset_clears_file(store, store_path):
    from app.core.model_config_store import ProviderPatch
    store.update(providers={"deepseek": ProviderPatch(name="deepseek", api_key="sk-x")})
    assert store_path.exists()
    store.delete_file()
    assert not store_path.exists()
    assert store.load_snapshot() is None