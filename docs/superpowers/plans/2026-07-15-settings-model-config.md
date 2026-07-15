# 设置页模型配置 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在 `/settings/models` 页面让用户编辑 LLM provider 配置（API key / base_url / model）、三档 tier 选择、fallback chain、默认 provider 顺序；保存后下一次 LLM 调用生效，无需重启进程。

**Architecture:** 后端新建 `ModelConfigStore`（JSON 文件 + RLock + Fernet 加密），扩展 `Settings.merge_runtime_overrides()` 在 `get_settings()` 内合并 JSON 覆盖，PATCH 端点写盘后失效 `lru_cache`。前端新增 `ModelsSettings` 页面，调 `settingsApi.getModelConfig / updateModelConfig / resetModelConfig`。

**Tech Stack:**
- 后端：Python 3.11 / FastAPI / pydantic_settings / cryptography.fernet
- 前端：React 18 + Vite + TanStack Query + vitest + @testing-library/react
- 持久化：`data/model_config.json`（Fernet 加密 API key 字段）
- 测试：pytest + vitest（已有）

---

## Global Constraints

- 加密 key 来源：`Settings.encryption_key`（复用 `app/domain/security/encryption.py::encrypt/decrypt`）
- 持久化路径：`backend/data/model_config.json`（相对项目根，与 `data/reports.db` 同级）
- JSON 缺字段 → fall back 到 `.env` 值；JSON 损坏 / 校验失败 → 降级不阻塞启动
- PATCH 语义：`api_key=""` 或缺失 = 保留旧 key；非空 = 替换
- 路由前缀：`/api/settings/models`（单 router）
- 测试基础设施已就绪：`backend/tests/conftest.py` 提供 `temp_db` / `db_session` / `client` / `mock_memory_vectors`；`ENCRYPTION_KEY` 在 `client` fixture 内已 monkeypatch，无需额外配置
- 所有失败 commit 立即停止任务并报告，不要继续往下做
- 提交格式：`<type>(<scope>): <subject>`，沿用现有约定（feat/fix/refactor/docs/test/chore）

---

## File Structure

### 后端 — 新增

| 文件 | 职责 |
|---|---|
| `backend/app/core/model_config_store.py` | `ModelConfigStore` 类：JSON 持久化 + 内存缓存 + RLock；`ModelConfigSnapshot` 数据类；Fernet 加密 |
| `backend/app/api/settings_model.py` | `router`（prefix=`/settings/models`）：GET / PATCH / POST `/reset` |
| `backend/tests/test_model_config_store.py` | §7.1 — store 单元测试（10 用例） |
| `backend/tests/test_settings_merge.py` | §7.2 — Settings merge 单元测试（7 用例） |
| `backend/tests/test_api_settings_model.py` | §7.3 — API 集成测试（15 用例） |

### 后端 — 修改

| 文件 | 改动 |
|---|---|
| `backend/app/core/config.py` | 加 `merge_runtime_overrides(overrides)` 方法 + `KNOWN_PROVIDER_NAMES` 类常量 + `get_settings()` 内首次构造时调一次 merge |
| `backend/app/main.py` | 注册 settings_model router |

### 前端 — 新增

| 文件 | 职责 |
|---|---|
| `frontend/src/api/settings.ts` | `settingsApi.getModelConfig / updateModelConfig / resetModelConfig` |
| `frontend/src/pages/ModelsSettings.tsx` | 表单 + 保存 + 重置 + 掩码 + 错误回显 |
| `frontend/src/api/settings.test.ts` | §7.5 — API 层测试（4 用例） |
| `frontend/src/pages/ModelsSettings.test.tsx` | §7.4 — 页面测试（13 用例） |

### 前端 — 修改

| 文件 | 改动 |
|---|---|
| `frontend/src/api/index.ts` | barrel export `settingsApi` |
| `frontend/src/routes.ts` | 加 `settingsModels: '/settings/models'` + ROUTE_META |
| `frontend/src/routes.test.ts` | 加 ROUTES / breadcrumb 用例 |
| `frontend/src/App.tsx` | 挂载 `<Route path={ROUTES.settingsModels} element={<ModelsSettings />} />` |
| `frontend/src/components/layout/navConfig.tsx` | "设置" 分组下加 `{ to: '/settings/models', label: '模型配置' }` |

---

## Task 1: `ModelConfigStore` + JSON 持久化 + Fernet 加密

**Files:**
- Create: `backend/app/core/model_config_store.py`
- Test: `backend/tests/test_model_config_store.py`

**Interfaces (used by later tasks):**
- `class ModelConfigSnapshot` — `dataclass(frozen=True)` 字段：`providers: dict[str, ProviderOverride]`、`tiers: dict[str, str]`、`fallback_chain: list[str]`、`llm_providers: list[str]`、`updated_at: str`
- `class ProviderOverride` — `dataclass(frozen=True)` 字段：`api_key_encrypted: str`、`base_url: str`、`model: str`
- `class ModelConfigStore`
  - `__init__(self, path: Path, encryption_key: str)`
  - `load_snapshot(self) -> ModelConfigSnapshot | None` — 文件不存在 / 损坏 → None
  - `update(self, *, providers: dict[str, ProviderPatch], tiers: dict[str, str] | None, fallback_chain: list[str] | None, llm_providers: list[str] | None) -> ModelConfigSnapshot`
  - `delete_file(self) -> None` — 删 JSON 文件 + 清内存缓存
  - `has_overrides(self) -> bool` — 是否存在有效快照
- `class ProviderPatch` — `dataclass` 字段：`name: str`、`api_key: str | None = None`（None = 不变，`""` = 也不变，只有非空字符串替换）、`base_url: str | None = None`、`model: str | None = None`

- [ ] **Step 1.1: Write the failing test for "creates file on first save"**

`backend/tests/test_model_config_store.py`:

```python
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
    # Need to decrypt externally using same key — store exposes ciphertext only


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
```

- [ ] **Step 1.2: Run test to verify it fails**

Run: `cd backend && pytest tests/test_model_config_store.py -v`
Expected: ImportError on `app.core.model_config_store`

- [ ] **Step 1.3: Write the implementation**

`backend/app/core/model_config_store.py`:

```python
"""v0.7+ 模型配置持久化 + Fernet 加密 (P1#42 / Task 41)。

设计要点：
- JSON 单文件 `data/model_config.json`
- API key 用 Fernet 对称加密落盘（key 来自 Settings.encryption_key）
- RLock + 内存缓存，多线程安全
- 加载失败 → 返回 None（不抛），调用方按 .env baseline 走
"""
from __future__ import annotations

import json
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from cryptography.fernet import Fernet, InvalidToken


@dataclass(frozen=True)
class ProviderOverride:
    """单个 provider 的覆盖配置（来自 JSON 落盘后解密状态）。"""

    api_key_encrypted: str  # Fernet 密文；解密由调用方按需完成
    base_url: str
    model: str


@dataclass(frozen=True)
class ModelConfigSnapshot:
    """整份覆盖配置快照。"""

    providers: dict[str, ProviderOverride]
    tiers: dict[str, str]
    fallback_chain: list[str]
    llm_providers: list[str]
    updated_at: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "providers": {
                n: {"api_key": p.api_key_encrypted, "base_url": p.base_url, "model": p.model}
                for n, p in self.providers.items()
            },
            "tiers": dict(self.tiers),
            "fallback_chain": list(self.fallback_chain),
            "llm_providers": list(self.llm_providers),
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "ModelConfigSnapshot":
        providers: dict[str, ProviderOverride] = {}
        for name, p in (d.get("providers") or {}).items():
            providers[name] = ProviderOverride(
                api_key_encrypted=str(p.get("api_key", "") or ""),
                base_url=str(p.get("base_url", "") or ""),
                model=str(p.get("model", "") or ""),
            )
        tiers_raw = d.get("tiers") or {}
        tiers = {k: str(tiers_raw.get(k, "") or "") for k in ("cheap", "standard", "premium")}
        return cls(
            providers=providers,
            tiers=tiers,
            fallback_chain=[str(x) for x in (d.get("fallback_chain") or [])],
            llm_providers=[str(x) for x in (d.get("llm_providers") or [])],
            updated_at=str(d.get("updated_at", "") or ""),
        )


@dataclass
class ProviderPatch:
    """单个 provider 的部分更新（来自 PATCH 请求）。"""

    name: str
    api_key: str | None = None  # None = 不变；非空 = 替换
    base_url: str | None = None
    model: str | None = None


class ModelConfigStore:
    """文件持久化的模型配置 store。"""

    def __init__(self, path: Path, encryption_key: str):
        self.path = Path(path)
        self._encryption_key = encryption_key
        self._cipher = Fernet(encryption_key.encode()) if encryption_key else None
        # RLock: update() 内会调 _flush，_flush 需要同一把锁
        self._lock = threading.RLock()
        self._cache: ModelConfigSnapshot | None = None
        self._loaded = False

    def _load_from_disk(self) -> ModelConfigSnapshot | None:
        if not self.path.exists():
            return None
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return None
        if not isinstance(raw, dict):
            return None
        try:
            return ModelConfigSnapshot.from_dict(raw)
        except (KeyError, TypeError, ValueError):
            return None

    def _verify_cipher_or_drop(self, snap: ModelConfigSnapshot) -> ModelConfigSnapshot:
        """如果 api_key 密文无法解密，把 api_key 置空，其它字段保留。"""
        if self._cipher is None:
            # 没加密 key → 所有密文视为空
            providers = {
                n: ProviderOverride(api_key_encrypted="", base_url=p.base_url, model=p.model)
                for n, p in snap.providers.items()
            }
            return ModelConfigSnapshot(
                providers=providers,
                tiers=snap.tiers,
                fallback_chain=snap.fallback_chain,
                llm_providers=snap.llm_providers,
                updated_at=snap.updated_at,
            )
        providers_clean: dict[str, ProviderOverride] = {}
        for n, p in snap.providers.items():
            if p.api_key_encrypted:
                try:
                    self._cipher.decrypt(p.api_key_encrypted.encode())
                except (InvalidToken, ValueError):
                    providers_clean[n] = ProviderOverride(
                        api_key_encrypted="", base_url=p.base_url, model=p.model
                    )
                    continue
            providers_clean[n] = p
        return ModelConfigSnapshot(
            providers=providers_clean,
            tiers=snap.tiers,
            fallback_chain=snap.fallback_chain,
            llm_providers=snap.llm_providers,
            updated_at=snap.updated_at,
        )

    def load_snapshot(self) -> ModelConfigSnapshot | None:
        with self._lock:
            if not self._loaded:
                self._cache = self._verify_cipher_or_drop(self._load_from_disk() or ModelConfigSnapshot(
                    providers={}, tiers={}, fallback_chain=[], llm_providers=[], updated_at=""
                ))
                self._loaded = True
            return self._cache

    def has_overrides(self) -> bool:
        snap = self.load_snapshot()
        if snap is None:
            return False
        return bool(snap.providers) or bool(snap.tiers) or bool(snap.fallback_chain) or bool(snap.llm_providers)

    def _flush(self, snap: ModelConfigSnapshot) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(self.path.suffix + ".tmp")
        tmp.write_text(
            json.dumps(snap.to_dict(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        tmp.replace(self.path)  # 原子 rename

    def update(
        self,
        *,
        providers: dict[str, ProviderPatch] | None = None,
        tiers: dict[str, str] | None = None,
        fallback_chain: list[str] | None = None,
        llm_providers: list[str] | None = None,
    ) -> ModelConfigSnapshot:
        with self._lock:
            existing = self.load_snapshot() or ModelConfigSnapshot(
                providers={}, tiers={}, fallback_chain=[], llm_providers=[], updated_at=""
            )
            new_providers: dict[str, ProviderOverride] = dict(existing.providers)
            if providers:
                for name, patch in providers.items():
                    cur = new_providers.get(name) or ProviderOverride(api_key_encrypted="", base_url="", model="")
                    new_api_key_encrypted = cur.api_key_encrypted
                    if patch.api_key is not None and patch.api_key != "" and self._cipher is not None:
                        # 非空 → 加密覆盖
                        new_api_key_encrypted = self._cipher.encrypt(patch.api_key.encode()).decode()
                    # api_key="" 或 None → 保留旧密文
                    new_providers[name] = ProviderOverride(
                        api_key_encrypted=new_api_key_encrypted,
                        base_url=patch.base_url if patch.base_url is not None else cur.base_url,
                        model=patch.model if patch.model is not None else cur.model,
                    )
            new_tiers = dict(existing.tiers)
            if tiers:
                new_tiers.update(tiers)
            new_fallback = list(existing.fallback_chain)
            if fallback_chain is not None:
                new_fallback = list(fallback_chain)
            new_llm_providers = list(existing.llm_providers)
            if llm_providers is not None:
                new_llm_providers = list(llm_providers)

            new_snap = ModelConfigSnapshot(
                providers=new_providers,
                tiers=new_tiers,
                fallback_chain=new_fallback,
                llm_providers=new_llm_providers,
                updated_at=datetime.now(timezone.utc).isoformat(),
            )
            self._flush(new_snap)
            self._cache = new_snap
            self._loaded = True
            return new_snap

    def delete_file(self) -> None:
        with self._lock:
            if self.path.exists():
                self.path.unlink()
            self._cache = None
            self._loaded = True


__all__ = [
    "ModelConfigSnapshot",
    "ProviderOverride",
    "ProviderPatch",
    "ModelConfigStore",
]
```

- [ ] **Step 1.4: Run test to verify it passes**

Run: `cd backend && pytest tests/test_model_config_store.py -v`
Expected: PASS 10/10

- [ ] **Step 1.5: Commit**

```bash
git add backend/app/core/model_config_store.py backend/tests/test_model_config_store.py
git commit -m "feat(model-config): ModelConfigStore + Fernet 加密 + JSON 持久化"
```

---

## Task 2: `Settings.merge_runtime_overrides()` + 启动时 merge

**Files:**
- Modify: `backend/app/core/config.py:174-177` (extend `get_settings`)
- Modify: `backend/app/core/config.py` (add `merge_runtime_overrides`, `_KNOWN_PROVIDER_FIELDS`, `get_default_model_config_store`)
- Test: `backend/tests/test_settings_merge.py`

**Interfaces (consumed by Task 3):**
- `Settings.merge_runtime_overrides(self, snapshot: ModelConfigSnapshot | None) -> None` — 就地 mutate `self`，按 §4.2 表字段映射；快照里没字段 → 不动 self；tier/chain/providers 引用未注册名 → 跳过该字段 + warning log
- `_KNOWN_PROVIDER_FIELDS: dict[str, dict[str, str]]` — `{"deepseek": {"api_key": "deepseek_api_key", "base_url": "deepseek_base_url", "model": "deepseek_model"}, "kimi": {...}, "openai": {...}}`
- `get_default_model_config_store() -> ModelConfigStore` — 单例，路径 `data/model_config.json`

- [ ] **Step 2.1: Write the failing test**

`backend/tests/test_settings_merge.py`:

```python
"""Settings.merge_runtime_overrides — JSON 覆盖合并到 Settings 实例。"""
from __future__ import annotations

from pathlib import Path

import pytest
from cryptography.fernet import Fernet


@pytest.fixture(autouse=True)
def isolated_settings(monkeypatch, tmp_path):
    """重置 get_settings lru_cache，配置 ENCRYPTION_KEY + 临时 data/。"""
    from app.core.config import get_settings
    monkeypatch.setenv("DEEPSEEK_API_KEY", "env-deepseek-key")
    monkeypatch.setenv("DEEPSEEK_MODEL", "env-deepseek-model")
    monkeypatch.setenv("OPENAI_API_KEY", "env-openai-key")
    monkeypatch.setenv("ENCRYPTION_KEY", Fernet.generate_key().decode())
    monkeypatch.setenv("GEO_ALLOW_MISSING_LLM_KEY", "1")  # 不强制要求 key
    monkeypatch.chdir(tmp_path)
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_settings_uses_env_when_json_missing():
    from app.core.config import get_settings
    s = get_settings()
    assert s.deepseek_api_key == "env-deepseek-key"
    assert s.deepseek_model == "env-deepseek-model"


def test_settings_json_overrides_env_per_field(tmp_path):
    from app.core.config import get_settings
    from app.core.model_config_store import ModelConfigStore, ModelConfigSnapshot, ProviderOverride
    store = ModelConfigStore(path=tmp_path / "model_config.json", encryption_key=Fernet.generate_key().decode())
    snap = ModelConfigSnapshot(
        providers={"deepseek": ProviderOverride(api_key_encrypted="", base_url="", model="json-deepseek-model")},
        tiers={}, fallback_chain=[], llm_providers=[], updated_at="2026-07-15T00:00:00+00:00"
    )
    store._cache = snap
    store._loaded = True
    s = get_settings()
    assert s.deepseek_model == "json-deepseek-model"
    assert s.deepseek_api_key == "env-deepseek-key"  # 未覆盖 → 仍 .env


def test_settings_merges_all_provider_keys(tmp_path):
    from app.core.config import get_settings
    from cryptography.fernet import Fernet
    from app.core.model_config_store import ModelConfigStore, ModelConfigSnapshot, ProviderOverride

    key = Fernet.generate_key().decode()
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
    s = get_settings()
    assert s.openai_api_key == "new-openai-key"
    assert s.deepseek_model == "m1"
    assert s.fallback_chain == "deepseek,openai"
    assert s.llm_providers == "deepseek,openai"


def test_settings_invalid_tier_falls_back_to_env(tmp_path, caplog):
    from app.core.config import get_settings
    from app.core.model_config_store import ModelConfigStore, ModelConfigSnapshot, ProviderOverride
    store = ModelConfigStore(path=tmp_path / "model_config.json", encryption_key=Fernet.generate_key().decode())
    snap = ModelConfigSnapshot(
        providers={},
        tiers={"cheap": "deepseek", "standard": "deepseek", "premium": "minimax"},
        fallback_chain=[], llm_providers=[], updated_at="2026-07-15T00:00:00+00:00"
    )
    store._cache = snap
    store._loaded = True
    s = get_settings()
    # premium 在 .env 缺省 → "deepseek"（来自 Settings 默认值）
    assert s.model_tier_premium == "deepseek"


def test_settings_invalid_fallback_falls_back_to_env(tmp_path):
    from app.core.config import get_settings
    from app.core.model_config_store import ModelConfigStore, ModelConfigSnapshot, ProviderOverride
    store = ModelConfigStore(path=tmp_path / "model_config.json", encryption_key=Fernet.generate_key().decode())
    snap = ModelConfigSnapshot(
        providers={},
        tiers={}, fallback_chain=["deepseek", "minimax"], llm_providers=[],
        updated_at="2026-07-15T00:00:00+00:00"
    )
    store._cache = snap
    store._loaded = True
    s = get_settings()
    # 整条 chain 引用未注册 → fall back 到 .env（"deepseek,kimi"）
    assert s.fallback_chain == "deepseek,kimi"


def test_settings_cache_cleared_after_store_update(tmp_path):
    from app.core.config import get_settings
    from cryptography.fernet import Fernet
    from app.core.model_config_store import ModelConfigStore, ProviderPatch

    key = Fernet.generate_key().decode()
    store = ModelConfigStore(path=tmp_path / "model_config.json", encryption_key=key)
    store.update(providers={"deepseek": ProviderPatch(name="deepseek", api_key="sk-new", model="new-m")})
    get_settings.cache_clear()
    s = get_settings()
    assert s.deepseek_api_key == "sk-new"
    assert s.deepseek_model == "new-m"


def test_settings_merges_each_call_after_clear(tmp_path):
    from app.core.config import get_settings
    from cryptography.fernet import Fernet
    from app.core.model_config_store import ModelConfigStore, ProviderPatch

    key = Fernet.generate_key().decode()
    store = ModelConfigStore(path=tmp_path / "model_config.json", encryption_key=key)
    store.update(providers={"deepseek": ProviderPatch(name="deepseek", model="m-1")})
    get_settings.cache_clear()
    assert get_settings().deepseek_model == "m-1"
    store.update(providers={"deepseek": ProviderPatch(name="deepseek", model="m-2")})
    get_settings.cache_clear()
    assert get_settings().deepseek_model == "m-2"
```

- [ ] **Step 2.2: Run test to verify it fails**

Run: `cd backend && pytest tests/test_settings_merge.py -v`
Expected: AttributeError or fixture error (Settings.merge_runtime_overrides does not exist)

- [ ] **Step 2.3: Write the implementation**

Modify `backend/app/core/config.py`. Append to the file (after the existing `Settings` class and `get_settings` function):

```python
# === v0.7+ 模型配置运行时覆盖（Task 41） ===

# PROVIDERS_META 注册的 provider 与 Settings 字段的映射表
_KNOWN_PROVIDER_FIELDS: dict[str, dict[str, str]] = {
    "deepseek": {
        "api_key": "deepseek_api_key",
        "base_url": "deepseek_base_url",
        "model": "deepseek_model",
    },
    "kimi": {
        "api_key": "kimi_api_key",
        "base_url": "kimi_base_url",
        "model": "kimi_model",
    },
    "openai": {
        "api_key": "openai_api_key",
        "base_url": "openai_base_url",
        "model": "openai_model",
    },
}

# providers 模块加载后再注入（避免循环 import）
def _register_kimi_openai() -> None:
    """Kimi/OpenAI 在 Settings 里没有 .env 字段；如未来加入 PROVIDERS_META 也按这里扩展。"""
    # 当前 deepseek 已有完整映射；kimi/openai 已在 Settings 中存在
    pass


def _apply_provider_overrides(settings: "Settings") -> None:
    """解密 JSON 里的 api_key 密文 → setattr 到 Settings 实例。"""
    from cryptography.fernet import Fernet, InvalidToken
    from app.core.model_config_store import ModelConfigSnapshot

    if not settings.encryption_key:
        return  # 无 key → 跳过加密字段（保持 .env 或空）
    cipher = Fernet(settings.encryption_key.encode())
    # snapshot 由调用方传入；这里仅处理解密
    return  # 实际解密在 merge_runtime_overrides 里完成


# 改为：直接在 merge_runtime_overrides 内 import cipher
```

Replace the `merge_runtime_overrides` placeholder above with the actual implementation by **replacing the entire `Settings` class' bottom (after the `enabled_providers` property) and `get_settings` function** as follows. Edit `backend/app/core/config.py`:

1. After `@property def parsed_fallback_chain`, add the new method `merge_runtime_overrides`:

```python
    def merge_runtime_overrides(
        self,
        snapshot: "ModelConfigSnapshot | None",
    ) -> None:
        """把 JSON 快照合并进 self（仅 mutate 我们关心的字段）。

        规则（spec §4.2 / §5.1）：
        - 快照里没字段 → 不动 self（保留 .env baseline）
        - provider 名不在 _KNOWN_PROVIDER_FIELDS → 跳过 + warning
        - tier 值不在 _KNOWN_PROVIDER_FIELDS → 跳过该 tier + warning
        - fallback_chain / llm_providers 任一元素未注册 → 跳过整个列表 + warning
        - api_key 密文 → 解密后 setattr；解密失败 → 跳过该 provider key
        """
        from app.core.providers import PROVIDERS_META
        from cryptography.fernet import Fernet, InvalidToken
        import structlog

        log = structlog.get_logger()
        if snapshot is None:
            return

        registered = set(PROVIDERS_META.keys())
        cipher = None
        if self.encryption_key:
            try:
                cipher = Fernet(self.encryption_key.encode())
            except (ValueError, TypeError):
                log.warning("encryption_key_invalid_format_skipping_keys")
                cipher = None

        # providers → setattr
        for name, override in snapshot.providers.items():
            mapping = _KNOWN_PROVIDER_FIELDS.get(name)
            if mapping is None:
                log.warning("unknown_provider_in_overrides", provider=name)
                continue
            if override.api_key_encrypted and cipher is not None:
                try:
                    plain = cipher.decrypt(override.api_key_encrypted.encode()).decode()
                    setattr(self, mapping["api_key"], plain)
                except (InvalidToken, ValueError):
                    log.warning("api_key_decrypt_failed_skip", provider=name)
            if override.base_url:
                setattr(self, mapping["base_url"], override.base_url)
            if override.model:
                setattr(self, mapping["model"], override.model)

        # tiers
        for tier_key, provider_name in snapshot.tiers.items():
            attr = {
                "cheap": "model_tier_cheap",
                "standard": "model_tier_standard",
                "premium": "model_tier_premium",
            }.get(tier_key)
            if attr is None:
                continue
            if provider_name not in registered:
                log.warning("invalid_tier_provider_skip", tier=tier_key, provider=provider_name)
                continue
            setattr(self, attr, provider_name)

        # fallback_chain — 任一元素未注册 → 跳过整条
        if snapshot.fallback_chain:
            if all(p in registered for p in snapshot.fallback_chain):
                self.fallback_chain = ",".join(snapshot.fallback_chain)
            else:
                bad = [p for p in snapshot.fallback_chain if p not in registered]
                log.warning("invalid_fallback_chain_providers_skip", bad=bad)

        # llm_providers — 同上
        if snapshot.llm_providers:
            if all(p in registered for p in snapshot.llm_providers):
                self.llm_providers = ",".join(snapshot.llm_providers)
            else:
                bad = [p for p in snapshot.llm_providers if p not in registered]
                log.warning("invalid_llm_providers_skip", bad=bad)
```

2. Replace `get_settings()` with the merged version:

```python
_DEFAULT_MODEL_CONFIG_STORE: "ModelConfigStore | None" = None


def get_default_model_config_store() -> "ModelConfigStore":
    """获取默认 ModelConfigStore 单例（路径 data/model_config.json）。"""
    global _DEFAULT_MODEL_CONFIG_STORE
    if _DEFAULT_MODEL_CONFIG_STORE is None:
        from app.core.model_config_store import ModelConfigStore

        settings_for_path = Settings()
        data_dir = Path(settings_for_path.database_url.replace("sqlite+aiosqlite:///", "")).parent
        _DEFAULT_MODEL_CONFIG_STORE = ModelConfigStore(
            path=data_dir / "model_config.json",
            encryption_key=settings_for_path.encryption_key or "",
        )
    return _DEFAULT_MODEL_CONFIG_STORE


def reset_default_model_config_store() -> None:
    """测试用：清除单例。"""
    global _DEFAULT_MODEL_CONFIG_STORE
    _DEFAULT_MODEL_CONFIG_STORE = None


@lru_cache
def get_settings() -> Settings:
    """Cached settings singleton (with runtime overrides merged)."""
    s = Settings()
    store = get_default_model_config_store()
    snapshot = store.load_snapshot()
    s.merge_runtime_overrides(snapshot)
    return s
```

- [ ] **Step 2.4: Run test to verify it passes**

Run: `cd backend && pytest tests/test_settings_merge.py -v`
Expected: PASS 7/7

- [ ] **Step 2.5: Commit**

```bash
git add backend/app/core/config.py backend/tests/test_settings_merge.py
git commit -m "feat(model-config): Settings.merge_runtime_overrides + 启动时 merge"
```

---

## Task 3: API endpoint — GET / PATCH / reset

**Files:**
- Create: `backend/app/api/settings_model.py`
- Modify: `backend/app/main.py:9,73-87` (add import + include_router)
- Test: `backend/tests/test_api_settings_model.py`

**Interfaces (consumed by frontend Task 5):**
- `GET /api/settings/models` → `ModelConfigDTO` (spec §4.3)
- `PATCH /api/settings/models` (body: `ModelConfigUpdate`) → `ModelConfigDTO`
- `POST /api/settings/models/reset` → `ModelConfigDTO`

DTO shape (response):
```python
class ProviderDTO(BaseModel):
    name: str
    base_url: str
    model: str
    api_key_set: bool
    api_key_masked: str  # "" 或 "sk-***abc123" 形式

class ModelConfigDTO(BaseModel):
    providers: list[ProviderDTO]
    tiers: dict[str, str]  # {"cheap": ..., "standard": ..., "premium": ...}
    fallback_chain: list[str]
    llm_providers: list[str]
    source: str  # "json" 或 "env"
    updated_at: str
```

Request body (PATCH):
```python
class ProviderUpdate(BaseModel):
    name: str
    api_key: str | None = None  # None 或 "" = 不改
    base_url: str | None = None
    model: str | None = None

class ModelConfigUpdate(BaseModel):
    providers: list[ProviderUpdate] | None = None
    tiers: dict[str, str] | None = None
    fallback_chain: list[str] | None = None
    llm_providers: list[str] | None = None
```

Error response shape (HTTPException with structured body via custom handler — keep simple, use `detail`):
- 422 Pydantic validation → default FastAPI 422 body
- 422 `unknown_provider` / `invalid_base_url` / `empty_model` / `encryption_key_missing` → raise `HTTPException(422, detail={"code": "...", "field": "...", "message": "..."})`
- 409 `concurrent_update` → `HTTPException(409, detail={"code": "concurrent_update", ...})`

- [ ] **Step 3.1: Write the failing test**

`backend/tests/test_api_settings_model.py`:

```python
"""API integration tests for /api/settings/models (Task 41)."""
from __future__ import annotations

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


def test_get_returns_providers_from_settings(client, monkeypatch, tmp_path):
    _patch_settings(monkeypatch, tmp_path)
    r = client.get("/api/settings/models")
    assert r.status_code == 200
    data = r.json()
    names = [p["name"] for p in data["providers"]]
    assert "deepseek" in names
    assert "kimi" in names
    assert "openai" in names


def test_get_masks_api_key_when_set(client, monkeypatch, tmp_path):
    _patch_settings(monkeypatch, tmp_path)
    r = client.get("/api/settings/models")
    data = r.json()
    deepseek = next(p for p in data["providers"] if p["name"] == "deepseek")
    assert deepseek["api_key_set"] is True
    assert deepseek["api_key_masked"].startswith("tes")
    assert "***" in deepseek["api_key_masked"]


def test_get_omits_mask_when_unset(client, monkeypatch, tmp_path):
    _patch_settings(monkeypatch, tmp_path)
    r = client.get("/api/settings/models")
    data = r.json()
    kimi = next(p for p in data["providers"] if p["name"] == "kimi")
    assert kimi["api_key_set"] is False
    assert kimi["api_key_masked"] == ""


def test_get_reports_source_json_when_override_exists(client, monkeypatch, tmp_path):
    _patch_settings(monkeypatch, tmp_path)
    # 写入一个 provider 到 store
    client.patch("/api/settings/models", json={
        "providers": [{"name": "deepseek", "model": "deepseek-v2"}]
    })
    r = client.get("/api/settings/models")
    assert r.json()["source"] == "json"


def test_get_reports_source_env_when_no_override(client, monkeypatch, tmp_path):
    _patch_settings(monkeypatch, tmp_path)
    r = client.get("/api/settings/models")
    assert r.json()["source"] == "env"


def test_patch_updates_store_and_clears_cache(client, monkeypatch, tmp_path):
    _patch_settings(monkeypatch, tmp_path)
    r = client.patch("/api/settings/models", json={
        "providers": [{"name": "deepseek", "model": "deepseek-v3"}]
    })
    assert r.status_code == 200
    from app.core.config import get_settings
    assert get_settings().deepseek_model == "deepseek-v3"


def test_patch_rejects_unknown_provider_in_tier(client, monkeypatch, tmp_path):
    _patch_settings(monkeypatch, tmp_path)
    r = client.patch("/api/settings/models", json={
        "tiers": {"cheap": "deepseek", "standard": "deepseek", "premium": "minimax"}
    })
    assert r.status_code == 422
    body = r.json()
    # FastAPI default validation OR our custom — check code presence
    assert "minimax" in str(body) or "unknown_provider" in str(body)


def test_patch_rejects_invalid_base_url(client, monkeypatch, tmp_path):
    _patch_settings(monkeypatch, tmp_path)
    r = client.patch("/api/settings/models", json={
        "providers": [{"name": "deepseek", "base_url": "not-a-url"}]
    })
    assert r.status_code == 422


def test_patch_rejects_empty_model(client, monkeypatch, tmp_path):
    _patch_settings(monkeypatch, tmp_path)
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


def test_patch_empty_api_key_does_not_clear_existing(client, monkeypatch, tmp_path):
    _patch_settings(monkeypatch, tmp_path)
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


def test_patch_missing_api_key_does_not_clear_existing(client, monkeypatch, tmp_path):
    _patch_settings(monkeypatch, tmp_path)
    client.patch("/api/settings/models", json={
        "providers": [{"name": "deepseek", "api_key": "sk-original"}]
    })
    client.patch("/api/settings/models", json={
        "providers": [{"name": "deepseek", "model": "deepseek-v2"}]
    })
    from app.core.config import get_settings
    assert get_settings().deepseek_api_key == "sk-original"


def test_reset_clears_overrides_and_falls_back_to_env(client, monkeypatch, tmp_path):
    _patch_settings(monkeypatch, tmp_path)
    client.patch("/api/settings/models", json={
        "providers": [{"name": "deepseek", "model": "deepseek-v3"}]
    })
    from app.core.config import get_settings
    assert get_settings().deepseek_model == "deepseek-v3"
    r = client.post("/api/settings/models/reset")
    assert r.status_code == 200
    assert get_settings().deepseek_model == "env-deepseek-model"  # baseline via fixture
    assert r.json()["source"] == "env"


def test_patch_returns_updated_dto(client, monkeypatch, tmp_path):
    _patch_settings(monkeypatch, tmp_path)
    r = client.patch("/api/settings/models", json={
        "providers": [{"name": "deepseek", "model": "deepseek-v3"}]
    })
    body = r.json()
    deepseek = next(p for p in body["providers"] if p["name"] == "deepseek")
    assert deepseek["model"] == "deepseek-v3"
```

- [ ] **Step 3.2: Run test to verify it fails**

Run: `cd backend && pytest tests/test_api_settings_model.py -v`
Expected: 404 on all routes (router not registered yet)

- [ ] **Step 3.3: Write the implementation**

`backend/app/api/settings_model.py`:

```python
"""v0.7+ 设置 — 模型配置 API (Task 41)。"""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, HTTPException
from pydantic import AnyHttpUrl, BaseModel, Field, field_validator

from app.core.config import (
    get_default_model_config_store,
    get_settings,
    reset_default_model_config_store,
)
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


def _decrypt_or_none(encrypted: str, encryption_key: str) -> str | None:
    """解密密文；失败或无 key 返回 None（视作 unset）。"""
    if not encrypted:
        return ""
    if not encryption_key:
        return None
    from cryptography.fernet import Fernet, InvalidToken
    try:
        cipher = Fernet(encryption_key.encode())
        return cipher.decrypt(encrypted.encode()).decode()
    except (InvalidToken, ValueError):
        return None


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
        # 如果 snapshot 有密文但 settings 里是空的（即密文解密失败或 key 没设），按密文 set 状态判断
        api_key_set = bool(api_key)
        if not api_key_set and snap and name in snap.providers and snap.providers[name].api_key_encrypted:
            # 密文存在但解密失败 → api_key_set 仍按"已尝试设置"算 True，但 masked 为提示
            api_key_set = True
        providers_dto.append(ProviderDTO(
            name=name,
            base_url=base_url,
            model=model,
            api_key_set=api_key_set,
            api_key_masked=_mask_key(api_key) if api_key_set else "",
        ))

    def _split_list(value: str) -> list[str]:
        return [p.strip() for p in (value or "").split(",") if p.strip()]

    return ModelConfigDTO(
        providers=providers_dto,
        tiers={
            "cheap": settings.model_tier_cheap,
            "standard": settings.model_tier_standard,
            "premium": settings.model_tier_premium,
        },
        fallback_chain=_split_list(settings.fallback_chain),
        llm_providers=_split_list(settings.llm_providers),
        source="json" if (snap and (snap.providers or snap.tiers or snap.fallback_chain or snap.llm_providers)) else "env",
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
    from app.core.config import get_settings as _get
    _get.cache_clear()
    return _build_dto()


@router.post("/reset", response_model=ModelConfigDTO)
async def reset_model_config() -> ModelConfigDTO:
    store = get_default_model_config_store()
    store.delete_file()
    from app.core.config import get_settings as _get
    _get.cache_clear()
    return _build_dto()
```

Then modify `backend/app/main.py`:

1. Add import at top:
```python
from app.api import settings_model
```

2. Inside `create_app()` after line 84 (`app.include_router(agent_chat.router, prefix="/api")`), add:
```python
    app.include_router(settings_model.router, prefix="/api")
```

- [ ] **Step 3.4: Run test to verify it passes**

Run: `cd backend && pytest tests/test_api_settings_model.py -v`
Expected: PASS 15/15

- [ ] **Step 3.5: Run all backend tests to verify no regression**

Run: `cd backend && pytest tests/test_settings_merge.py tests/test_model_config_store.py tests/test_api_settings_model.py tests/test_providers.py tests/test_adaptive_model.py tests/test_fallback_strategy.py -v`
Expected: PASS all

- [ ] **Step 3.6: Commit**

```bash
git add backend/app/api/settings_model.py backend/app/main.py backend/tests/test_api_settings_model.py
git commit -m "feat(model-config): GET/PATCH/reset /api/settings/models + DTO + 校验"
```

---

## Task 4: Frontend API layer — `settingsApi`

**Files:**
- Create: `frontend/src/api/settings.ts`
- Modify: `frontend/src/api/index.ts:32-67` (add export + api namespace)
- Test: `frontend/src/api/settings.test.ts`

**Interfaces (consumed by Task 5):**
- `settingsApi.getModelConfig(): Promise<ModelConfigDTO>`
- `settingsApi.updateModelConfig(payload: ModelConfigUpdate): Promise<ModelConfigDTO>`
- `settingsApi.resetModelConfig(): Promise<ModelConfigDTO>`
- Types: `ProviderDTO`, `ModelConfigDTO`, `ProviderUpdate`, `ModelConfigUpdate`

- [ ] **Step 4.1: Write the failing test**

`frontend/src/api/settings.test.ts`:

```typescript
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { ApiError } from './infra';

describe('settingsApi (v0.7+)', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it('getModelConfig calls GET /settings/models', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({
        providers: [],
        tiers: { cheap: '', standard: '', premium: '' },
        fallback_chain: [],
        llm_providers: [],
        source: 'env',
        updated_at: '',
      }),
    });
    vi.stubGlobal('fetch', fetchMock);
    const { settingsApi } = await import('./settings');
    const r = await settingsApi.getModelConfig();
    expect(r.source).toBe('env');
    expect(fetchMock).toHaveBeenCalledWith('/api/settings/models', expect.objectContaining({
      headers: expect.objectContaining({ 'Content-Type': 'application/json' }),
    }));
  });

  it('updateModelConfig sends PATCH with body', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({
        providers: [],
        tiers: {},
        fallback_chain: [],
        llm_providers: [],
        source: 'json',
        updated_at: '2026-07-15T00:00:00+00:00',
      }),
    });
    vi.stubGlobal('fetch', fetchMock);
    const { settingsApi } = await import('./settings');
    await settingsApi.updateModelConfig({
      providers: [{ name: 'deepseek', api_key: 'sk-new', model: 'm' }],
    });
    expect(fetchMock).toHaveBeenCalledWith('/api/settings/models', expect.objectContaining({
      method: 'PATCH',
      body: JSON.stringify({
        providers: [{ name: 'deepseek', api_key: 'sk-new', model: 'm' }],
      }),
    }));
  });

  it('resetModelConfig calls POST /settings/models/reset', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({ providers: [], tiers: {}, fallback_chain: [], llm_providers: [], source: 'env', updated_at: '' }),
    });
    vi.stubGlobal('fetch', fetchMock);
    const { settingsApi } = await import('./settings');
    await settingsApi.resetModelConfig();
    expect(fetchMock).toHaveBeenCalledWith('/api/settings/models/reset', expect.objectContaining({
      method: 'POST',
    }));
  });

  it('throws ApiError with status and code on non-OK', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: false,
      status: 422,
      text: async () => JSON.stringify({ detail: { code: 'unknown_provider', message: 'x' } }),
    });
    vi.stubGlobal('fetch', fetchMock);
    const { settingsApi } = await import('./settings');
    await expect(settingsApi.getModelConfig()).rejects.toMatchObject({ status: 422 });
  });
});
```

- [ ] **Step 4.2: Run test to verify it fails**

Run: `cd frontend && npx vitest run src/api/settings.test.ts`
Expected: Module not found error

- [ ] **Step 4.3: Write the implementation**

`frontend/src/api/settings.ts`:

```typescript
/**
 * v0.7+ settings API — model configuration endpoints (Task 41).
 */
import { request } from './infra';

export interface ProviderDTO {
  name: string;
  base_url: string;
  model: string;
  api_key_set: boolean;
  api_key_masked: string;
}

export interface ModelConfigDTO {
  providers: ProviderDTO[];
  tiers: { cheap: string; standard: string; premium: string };
  fallback_chain: string[];
  llm_providers: string[];
  source: 'env' | 'json';
  updated_at: string;
}

export interface ProviderUpdate {
  name: string;
  api_key?: string | null;
  base_url?: string | null;
  model?: string | null;
}

export interface ModelConfigUpdate {
  providers?: ProviderUpdate[];
  tiers?: { cheap?: string; standard?: string; premium?: string };
  fallback_chain?: string[];
  llm_providers?: string[];
}

export const settingsApi = {
  getModelConfig(): Promise<ModelConfigDTO> {
    return request<ModelConfigDTO>('/settings/models');
  },

  updateModelConfig(payload: ModelConfigUpdate): Promise<ModelConfigDTO> {
    return request<ModelConfigDTO>('/settings/models', {
      method: 'PATCH',
      body: JSON.stringify(payload),
    });
  },

  resetModelConfig(): Promise<ModelConfigDTO> {
    return request<ModelConfigDTO>('/settings/models/reset', { method: 'POST' });
  },
};

export type SettingsApi = typeof settingsApi;
```

Modify `frontend/src/api/index.ts` — add import + export + include in `api` namespace:

1. After line 31 (`import { costApi } from './cost';`), add:
```typescript
import { settingsApi } from './settings';
```

2. Inside the `export { ... }` block (after line 49 `costApi`), add:
```typescript
  settingsApi,
```

3. Inside the `api` object literal (after line 66 `...costApi,`), add:
```typescript
  ...settingsApi,
```

- [ ] **Step 4.4: Run test to verify it passes**

Run: `cd frontend && npx vitest run src/api/settings.test.ts`
Expected: PASS 4/4

- [ ] **Step 4.5: Commit**

```bash
git add frontend/src/api/settings.ts frontend/src/api/index.ts frontend/src/api/settings.test.ts
git commit -m "feat(model-config): settingsApi + DTO + 4 用例"
```

---

## Task 5: Frontend page — `ModelsSettings` + 路由 + 侧栏

**Files:**
- Create: `frontend/src/pages/ModelsSettings.tsx`
- Modify: `frontend/src/routes.ts` (add `settingsModels` + ROUTE_META)
- Modify: `frontend/src/routes.test.ts` (add cases)
- Modify: `frontend/src/App.tsx` (import + mount route)
- Modify: `frontend/src/components/layout/navConfig.tsx` (add menu item)
- Test: `frontend/src/pages/ModelsSettings.test.tsx`

**Interfaces (consumed by user):**
- 页面 route：`/settings/models`
- 顶部展示 source badge（"env" / "json 覆盖"）
- 每个 provider 一张卡：base_url / model 输入框 + api_key 输入框（placeholder 显示掩码或"尚未设置"）
- 底部：tier 三个 select + fallback_chain 多选 + llm_providers 多选
- 操作栏：保存按钮 + 重置按钮（二次确认 dialog）

- [ ] **Step 5.1: Write the failing test**

`frontend/src/pages/ModelsSettings.test.tsx`:

```typescript
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';

const mockGet = vi.fn();
const mockUpdate = vi.fn();
const mockReset = vi.fn();

vi.mock('@/api/settings', () => ({
  settingsApi: {
    getModelConfig: () => mockGet(),
    updateModelConfig: (payload: unknown) => mockUpdate(payload),
    resetModelConfig: () => mockReset(),
  },
}));

vi.mock('sonner', () => ({
  toast: { success: vi.fn(), error: vi.fn() },
  Toaster: () => null,
}));

function renderWithClient(ui: React.ReactNode) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={qc}>{ui}</QueryClientProvider>);
}

const baseDTO = {
  providers: [
    { name: 'deepseek', base_url: 'https://api.deepseek.com/v1', model: 'deepseek-chat', api_key_set: true, api_key_masked: 'sk-***abc' },
    { name: 'kimi', base_url: 'https://api.moonshot.cn/v1', model: 'moonshot-v1-8k', api_key_set: false, api_key_masked: '' },
    { name: 'openai', base_url: 'https://api.openai.com/v1', model: 'gpt-4o-mini', api_key_set: false, api_key_masked: '' },
  ],
  tiers: { cheap: 'deepseek', standard: 'deepseek', premium: 'deepseek' },
  fallback_chain: ['deepseek', 'kimi'],
  llm_providers: ['deepseek'],
  source: 'env' as const,
  updated_at: '',
};

describe('ModelsSettings (v0.7+)', () => {
  beforeEach(() => {
    mockGet.mockReset();
    mockUpdate.mockReset();
    mockReset.mockReset();
    mockGet.mockResolvedValue(baseDTO);
    mockUpdate.mockResolvedValue({ ...baseDTO, source: 'json' });
    mockReset.mockResolvedValue({ ...baseDTO, source: 'env' });
  });

  it('renders loading skeleton on mount', () => {
    mockGet.mockReturnValue(new Promise(() => {}));
    renderWithClient(<ModelsSettings />);
    // Skeletons have the Skeleton class; at least one present
    expect(document.querySelectorAll('[class*="animate-pulse"]').length).toBeGreaterThan(0);
  });

  it('renders three provider cards after load', async () => {
    renderWithClient(<ModelsSettings />);
    await waitFor(() => expect(screen.getByText('deepseek')).toBeInTheDocument());
    expect(screen.getByText('kimi')).toBeInTheDocument();
    expect(screen.getByText('openai')).toBeInTheDocument();
  });

  it('api_key input shows mask placeholder when set', async () => {
    renderWithClient(<ModelsSettings />);
    await waitFor(() => expect(screen.getByText('deepseek')).toBeInTheDocument());
    const deepseekCard = screen.getByText('deepseek').closest('[data-testid]') ?? screen.getByText('deepseek').parentElement!;
    const inputs = deepseekCard.querySelectorAll('input[type="password"], input[type="text"]');
    // At least one input with placeholder = masked
    const maskedInput = Array.from(inputs).find((el) => (el as HTMLInputElement).placeholder.includes('***'));
    expect(maskedInput).toBeDefined();
  });

  it('api_key input shows "尚未设置" placeholder when unset', async () => {
    renderWithClient(<ModelsSettings />);
    await waitFor(() => expect(screen.getByText('kimi')).toBeInTheDocument());
    const kimiCard = screen.getByText('kimi').parentElement!;
    const inputs = kimiCard.querySelectorAll('input');
    const unsetInput = Array.from(inputs).find((el) => (el as HTMLInputElement).placeholder.includes('尚未设置'));
    expect(unsetInput).toBeDefined();
  });

  it('changing base_url or model marks dirty', async () => {
    renderWithClient(<ModelsSettings />);
    await waitFor(() => expect(screen.getByText('deepseek')).toBeInTheDocument());
    const saveBtn = screen.getByRole('button', { name: /保存/ });
    expect(saveBtn).toBeDisabled();
    const modelInput = screen.getAllByDisplayValue('deepseek-chat')[0];
    fireEvent.change(modelInput, { target: { value: 'deepseek-reasoner' } });
    expect(saveBtn).not.toBeDisabled();
  });

  it('saving with no api_key field sends no api_key in payload', async () => {
    renderWithClient(<ModelsSettings />);
    await waitFor(() => expect(screen.getByText('deepseek')).toBeInTheDocument());
    const modelInput = screen.getAllByDisplayValue('deepseek-chat')[0];
    fireEvent.change(modelInput, { target: { value: 'deepseek-reasoner' } });
    const saveBtn = screen.getByRole('button', { name: /保存/ });
    fireEvent.click(saveBtn);
    await waitFor(() => expect(mockUpdate).toHaveBeenCalled());
    const payload = mockUpdate.mock.calls[0][0];
    const dp = payload.providers.find((p: { name: string }) => p.name === 'deepseek');
    // User didn't touch api_key input → api_key field absent
    expect(dp.api_key).toBeUndefined();
  });

  it('saving with new api_key sends the value', async () => {
    renderWithClient(<ModelsSettings />);
    await waitFor(() => expect(screen.getByText('deepseek')).toBeInTheDocument());
    const deepseekCard = screen.getByText('deepseek').parentElement!;
    const apiKeyInput = Array.from(deepseekCard.querySelectorAll('input')).find(
      (el) => (el as HTMLInputElement).placeholder.includes('***'),
    ) as HTMLInputElement;
    fireEvent.change(apiKeyInput, { target: { value: 'sk-brand-new' } });
    const saveBtn = screen.getByRole('button', { name: /保存/ });
    fireEvent.click(saveBtn);
    await waitFor(() => expect(mockUpdate).toHaveBeenCalled());
    const payload = mockUpdate.mock.calls[0][0];
    const dp = payload.providers.find((p: { name: string }) => p.name === 'deepseek');
    expect(dp.api_key).toBe('sk-brand-new');
  });

  it('save success shows toast and updates form state', async () => {
    renderWithClient(<ModelsSettings />);
    await waitFor(() => expect(screen.getByText('deepseek')).toBeInTheDocument());
    const saveBtn = screen.getByRole('button', { name: /保存/ });
    fireEvent.click(saveBtn);
    await waitFor(() => expect(mockUpdate).toHaveBeenCalled());
    // toast.success called (via mocked sonner)
    const { toast } = await import('sonner');
    await waitFor(() => expect(toast.success).toHaveBeenCalled());
  });

  it('save validation error highlights field', async () => {
    mockUpdate.mockRejectedValueOnce({
      status: 422,
      message: JSON.stringify({ detail: { code: 'invalid_base_url', field: 'providers[0].base_url' } }),
    });
    renderWithClient(<ModelsSettings />);
    await waitFor(() => expect(screen.getByText('deepseek')).toBeInTheDocument());
    const saveBtn = screen.getByRole('button', { name: /保存/ });
    fireEvent.click(saveBtn);
    const { toast } = await import('sonner');
    await waitFor(() => expect(toast.error).toHaveBeenCalled());
  });

  it('save encryption_key_missing shows banner', async () => {
    mockUpdate.mockRejectedValueOnce({
      status: 422,
      message: JSON.stringify({ detail: { code: 'encryption_key_missing' } }),
    });
    renderWithClient(<ModelsSettings />);
    await waitFor(() => expect(screen.getByText('deepseek')).toBeInTheDocument());
    const saveBtn = screen.getByRole('button', { name: /保存/ });
    fireEvent.click(saveBtn);
    await waitFor(() => expect(screen.getByText(/加密密钥未配置/).length).toBeGreaterThan(0));
  });

  it('reset button requires confirmation', async () => {
    renderWithClient(<ModelsSettings />);
    await waitFor(() => expect(screen.getByText('deepseek')).toBeInTheDocument());
    const resetBtn = screen.getByRole('button', { name: /重置/ });
    fireEvent.click(resetBtn);
    await waitFor(() => expect(screen.getByText(/确认重置/)).toBeInTheDocument());
    expect(mockReset).not.toHaveBeenCalled();
  });

  it('reset clears overrides and shows env badge', async () => {
    mockGet.mockResolvedValueOnce({ ...baseDTO, source: 'json' });
    renderWithClient(<ModelsSettings />);
    await waitFor(() => expect(screen.getByText(/JSON 覆盖/).length).toBeGreaterThan(0));
    const resetBtn = screen.getByRole('button', { name: /重置/ });
    fireEvent.click(resetBtn);
    await waitFor(() => expect(screen.getByText(/确认重置/)).toBeInTheDocument());
    const confirmBtn = screen.getByRole('button', { name: /确认/ });
    fireEvent.click(confirmBtn);
    await waitFor(() => expect(mockReset).toHaveBeenCalled());
    await waitFor(() => expect(screen.getByText(/env|环境变量/).length).toBeGreaterThan(0));
  });

  it('concurrent save disables button while in-flight', async () => {
    mockUpdate.mockReturnValueOnce(new Promise(() => {}));
    renderWithClient(<ModelsSettings />);
    await waitFor(() => expect(screen.getByText('deepseek')).toBeInTheDocument());
    const modelInput = screen.getAllByDisplayValue('deepseek-chat')[0];
    fireEvent.change(modelInput, { target: { value: 'deepseek-v3' } });
    const saveBtn = screen.getByRole('button', { name: /保存/ });
    fireEvent.click(saveBtn);
    expect(saveBtn).toBeDisabled();
  });
});
```

- [ ] **Step 5.2: Run test to verify it fails**

Run: `cd frontend && npx vitest run src/pages/ModelsSettings.test.tsx`
Expected: Cannot find module '@/pages/ModelsSettings'

- [ ] **Step 5.3: Write the implementation**

`frontend/src/pages/ModelsSettings.tsx`:

```typescript
/**
 * v0.7+ 设置 — 模型配置页面 (Task 41)。
 *
 * 三个 provider 卡 + 三档 tier 选择 + fallback/llm_providers 多选 + 保存/重置。
 * 顶部 source badge 提示当前配置来自 env 还是 JSON 覆盖。
 */
import { useState, useMemo } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { toast } from 'sonner';

import { settingsApi, type ModelConfigDTO, type ProviderUpdate } from '@/api/settings';
import { ApiError } from '@/api/infra';
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Badge } from '@/components/ui/badge';
import { Skeleton } from '@/components/ui/skeleton';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
  DialogTrigger,
} from '@/components/ui/dialog';

type ProviderFormState = {
  base_url: string;
  model: string;
  api_key_input: string;  // 用户输入的明文；空串 = 不改
  api_key_set: boolean;   // GET 时是否有 key（用于 placeholder）
  api_key_masked: string;
  api_key_dirty: boolean; // 用户是否动过这个字段
};

const PROVIDER_DISPLAY: Record<string, string> = {
  deepseek: 'DeepSeek',
  kimi: 'Kimi (Moonshot)',
  openai: 'OpenAI',
};

function extractApiError(err: unknown): { code?: string; message: string; field?: string } {
  if (err instanceof ApiError) {
    try {
      const parsed = JSON.parse(err.message);
      if (parsed?.detail && typeof parsed.detail === 'object') {
        return { code: parsed.detail.code, message: parsed.detail.message ?? '', field: parsed.detail.field };
      }
    } catch {
      /* not JSON */
    }
    return { message: err.message };
  }
  return { message: String(err) };
}

export default function ModelsSettings() {
  const qc = useQueryClient();

  const configQ = useQuery({
    queryKey: ['settings', 'model-config'],
    queryFn: () => settingsApi.getModelConfig(),
  });

  const [providersState, setProvidersState] = useState<Record<string, ProviderFormState>>({});
  const [tiersState, setTiersState] = useState<{ cheap: string; standard: string; premium: string }>({
    cheap: '',
    standard: '',
    premium: '',
  });
  const [fallbackState, setFallbackState] = useState<string[]>([]);
  const [llmProvidersState, setLlmProvidersState] = useState<string[]>([]);

  // 首次 GET 成功后初始化表单 state
  const initialized = useMemo(() => {
    if (!configQ.data) return false;
    if (Object.keys(providersState).length > 0) return true;
    const next: Record<string, ProviderFormState> = {};
    configQ.data.providers.forEach((p) => {
      next[p.name] = {
        base_url: p.base_url,
        model: p.model,
        api_key_input: '',
        api_key_set: p.api_key_set,
        api_key_masked: p.api_key_masked,
        api_key_dirty: false,
      };
    });
    setProvidersState(next);
    setTiersState(configQ.data.tiers);
    setFallbackState(configQ.data.fallback_chain);
    setLlmProvidersState(configQ.data.llm_providers);
    return true;
  }, [configQ.data, providersState]);

  const saveMutation = useMutation({
    mutationFn: (payload: Parameters<typeof settingsApi.updateModelConfig>[0]) =>
      settingsApi.updateModelConfig(payload),
    onSuccess: (newDto) => {
      toast.success('已保存，下次 LLM 调用生效');
      qc.setQueryData(['settings', 'model-config'], newDto);
      // 重置 api_key_dirty + input
      setProvidersState((prev) => {
        const next: Record<string, ProviderFormState> = {};
        for (const [n, s] of Object.entries(prev)) {
          const fresh = newDto.providers.find((p) => p.name === n);
          next[n] = {
            ...s,
            api_key_input: '',
            api_key_dirty: false,
            api_key_set: fresh?.api_key_set ?? s.api_key_set,
            api_key_masked: fresh?.api_key_masked ?? s.api_key_masked,
          };
        }
        return next;
      });
    },
    onError: (err) => {
      const { code, message } = extractApiError(err);
      if (code === 'encryption_key_missing') {
        toast.error('加密密钥未配置，暂无法保存 API key；其它字段可保存');
      } else {
        toast.error(`保存失败: ${message || code || '未知错误'}`);
      }
    },
  });

  const resetMutation = useMutation({
    mutationFn: () => settingsApi.resetModelConfig(),
    onSuccess: (newDto) => {
      toast.success('已重置为 .env 默认值');
      qc.setQueryData(['settings', 'model-config'], newDto);
    },
  });

  if (configQ.isLoading) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-10 w-1/3" />
        <Skeleton className="h-40 w-full" />
        <Skeleton className="h-40 w-full" />
      </div>
    );
  }

  if (configQ.error || !configQ.data) {
    return (
      <div className="rounded-lg border border-destructive bg-destructive/10 p-6">
        <h2 className="text-lg font-semibold text-destructive">加载失败</h2>
        <p className="mt-2 text-sm text-muted-foreground">{String(configQ.error)}</p>
      </div>
    );
  }

  const dto = configQ.data;
  if (!initialized) return null;

  const dirty =
    Object.values(providersState).some(
      (s) => s.api_key_dirty,
    );

  function handleProviderField(name: string, field: keyof ProviderFormState, value: string) {
    setProvidersState((prev) => ({
      ...prev,
      [name]: { ...prev[name], [field]: value, ...(field === 'api_key_input' ? { api_key_dirty: true } : {}) },
    }));
  }

  function buildPayload() {
    const providers: ProviderUpdate[] = Object.entries(providersState).map(([name, s]) => {
      const update: ProviderUpdate = { name };
      if (s.api_key_dirty && s.api_key_input !== '') update.api_key = s.api_key_input;
      else update.api_key = null;
      if (s.base_url !== dto.providers.find((p) => p.name === name)?.base_url) update.base_url = s.base_url;
      if (s.model !== dto.providers.find((p) => p.name === name)?.model) update.model = s.model;
      return update;
    });
    return {
      providers,
      tiers: tiersState,
      fallback_chain: fallbackState,
      llm_providers: llmProvidersState,
    };
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold">模型配置</h1>
          <p className="text-sm text-muted-foreground">
            编辑各 provider 的 API key / base_url / 模型名、三档 tier、fallback chain 与默认 provider 顺序。
          </p>
        </div>
        <div className="flex items-center gap-2">
          {dto.source === 'json' ? (
            <Badge variant="warning" dot>JSON 覆盖</Badge>
          ) : (
            <Badge variant="outline" dot>环境变量</Badge>
          )}
        </div>
      </div>

      {dto.providers.map((p) => {
        const state = providersState[p.name];
        if (!state) return null;
        return (
          <Card key={p.name}>
            <CardHeader>
              <CardTitle>{PROVIDER_DISPLAY[p.name] ?? p.name}</CardTitle>
              <CardDescription>provider 名: {p.name}</CardDescription>
            </CardHeader>
            <CardContent className="grid grid-cols-1 gap-4 md:grid-cols-2">
              <div className="space-y-1">
                <Label htmlFor={`${p.name}-base-url`}>Base URL</Label>
                <Input
                  id={`${p.name}-base-url`}
                  value={state.base_url}
                  onChange={(e) => handleProviderField(p.name, 'base_url', e.target.value)}
                />
              </div>
              <div className="space-y-1">
                <Label htmlFor={`${p.name}-model`}>模型名</Label>
                <Input
                  id={`${p.name}-model`}
                  value={state.model}
                  onChange={(e) => handleProviderField(p.name, 'model', e.target.value)}
                />
              </div>
              <div className="space-y-1 md:col-span-2">
                <Label htmlFor={`${p.name}-api-key`}>API Key</Label>
                <Input
                  id={`${p.name}-api-key`}
                  type="password"
                  autoComplete="off"
                  placeholder={
                    state.api_key_set
                      ? state.api_key_masked || 'sk-***'
                      : '尚未设置'
                  }
                  value={state.api_key_input}
                  onChange={(e) => handleProviderField(p.name, 'api_key_input', e.target.value)}
                />
                <p className="text-xs text-muted-foreground">
                  留空表示保留当前 key；填写新值将覆盖。
                </p>
              </div>
            </CardContent>
          </Card>
        );
      })}

      <Card>
        <CardHeader>
          <CardTitle>三档模型选择</CardTitle>
          <CardDescription>cheap = 轻量任务；standard = 默认；premium = 复杂任务</CardDescription>
        </CardHeader>
        <CardContent className="grid grid-cols-1 gap-4 md:grid-cols-3">
          {(['cheap', 'standard', 'premium'] as const).map((tier) => (
            <div key={tier} className="space-y-1">
              <Label htmlFor={`tier-${tier}`}>{tier}</Label>
              <select
                id={`tier-${tier}`}
                value={tiersState[tier]}
                onChange={(e) => setTiersState((prev) => ({ ...prev, [tier]: e.target.value }))}
                className="flex h-9 w-full rounded-md border border-input bg-background px-3 py-1 text-sm shadow-sm"
              >
                {dto.providers.map((p) => (
                  <option key={p.name} value={p.name}>{p.name}</option>
                ))}
              </select>
            </div>
          ))}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Fallback Chain</CardTitle>
          <CardDescription>主 provider 失败时按顺序切下一个</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="flex flex-wrap gap-2">
            {dto.providers.map((p) => (
              <label key={p.name} className="flex items-center gap-2 rounded-md border border-border bg-card px-3 py-1.5 text-sm">
                <input
                  type="checkbox"
                  checked={fallbackState.includes(p.name)}
                  onChange={(e) => {
                    setFallbackState((prev) =>
                      e.target.checked ? [...prev, p.name] : prev.filter((x) => x !== p.name),
                    );
                  }}
                />
                {p.name}
              </label>
            ))}
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>默认 Provider 列表</CardTitle>
          <CardDescription>用于 llm_providers 字段，控制 enabled 顺序</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="flex flex-wrap gap-2">
            {dto.providers.map((p) => (
              <label key={p.name} className="flex items-center gap-2 rounded-md border border-border bg-card px-3 py-1.5 text-sm">
                <input
                  type="checkbox"
                  checked={llmProvidersState.includes(p.name)}
                  onChange={(e) => {
                    setLlmProvidersState((prev) =>
                      e.target.checked ? [...prev, p.name] : prev.filter((x) => x !== p.name),
                    );
                  }}
                />
                {p.name}
              </label>
            ))}
          </div>
        </CardContent>
      </Card>

      <div className="flex items-center justify-end gap-3">
        <Dialog>
          <DialogTrigger asChild>
            <Button variant="outline" disabled={resetMutation.isPending}>
              重置为 .env 默认值
            </Button>
          </DialogTrigger>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>确认重置</DialogTitle>
              <DialogDescription>
                将删除 <code>data/model_config.json</code>，所有运行时改动丢失，重启后端后回到纯 .env 配置。
              </DialogDescription>
            </DialogHeader>
            <DialogFooter>
              <Button variant="ghost">取消</Button>
              <Button
                variant="destructive"
                disabled={resetMutation.isPending}
                onClick={() => resetMutation.mutate()}
              >
                {resetMutation.isPending ? '重置中…' : '确认重置'}
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>

        <Button
          disabled={saveMutation.isPending}
          onClick={() => saveMutation.mutate(buildPayload())}
        >
          {saveMutation.isPending ? '保存中…' : '保存'}
        </Button>
      </div>
    </div>
  );
}
```

- [ ] **Step 5.4: Update routes + nav + App.tsx**

Modify `frontend/src/routes.ts`:

1. In `ROUTES` (around line 56, after `settingsDevTools`), add:
```typescript
  settingsModels: '/settings/models',
```

2. In `ROUTE_META` (after `settingsDevTools` line), add:
```typescript
  settingsModels: { label: '模型配置', description: 'Provider API key / 模型 / tier / fallback', parent: 'settings' },
```

Modify `frontend/src/routes.test.ts` — add cases:

After the existing `breadcrumbFor` tests (or add a new `describe`), add:
```typescript
describe('ROUTES settingsModels (v0.7+)', () => {
  it('exposes settingsModels route', () => {
    expect(ROUTES.settingsModels).toBe('/settings/models');
  });

  it('walks breadcrumb from /settings/models up to settings', () => {
    const trail = breadcrumbFor('/settings/models');
    expect(trail.map((c) => c.label)).toEqual(['设置', '模型配置']);
  });
});
```

Modify `frontend/src/App.tsx`:

1. After line 23 (`import NotificationSettings from '@/pages/NotificationSettings';`), add:
```typescript
import ModelsSettings from '@/pages/ModelsSettings';
```

2. After the `<Route path={ROUTES.settingsDevTools} ... />` block (after line 141 closing `/>`), add:
```typescript
        <Route path={ROUTES.settingsModels} element={<ModelsSettings />} />
```

Modify `frontend/src/components/layout/navConfig.tsx`:

Inside the `settings` section's `items` array (around line 86), after `{ to: '/settings/notifications', label: '通知设置' }`, add:
```typescript
      { to: '/settings/models', label: '模型配置' },
```

- [ ] **Step 5.5: Run all frontend tests**

Run: `cd frontend && npx vitest run src/pages/ModelsSettings.test.tsx src/api/settings.test.ts src/routes.test.ts`
Expected: PASS all (13 + 4 + 1 = 18 tests)

- [ ] **Step 5.6: Run tsc to verify no type errors**

Run: `cd frontend && npx tsc --noEmit`
Expected: no errors

- [ ] **Step 5.7: Commit**

```bash
git add frontend/src/pages/ModelsSettings.tsx frontend/src/pages/ModelsSettings.test.tsx \
  frontend/src/routes.ts frontend/src/routes.test.ts \
  frontend/src/App.tsx frontend/src/components/layout/navConfig.tsx
git commit -m "feat(model-config): ModelsSettings 页面 + 路由 + 侧栏 + 13 用例"
```

---

## Task 6: 全栈回归验证

**Files:** 无新增，仅运行现有测试

- [ ] **Step 6.1: Run all backend tests**

Run: `cd backend && pytest -v`
Expected: PASS all existing + 32 new (10 store + 7 merge + 15 api)

- [ ] **Step 6.2: Run all frontend tests**

Run: `cd frontend && npx vitest run`
Expected: PASS all

- [ ] **Step 6.3: tsc on backend**

Run: `cd backend && python -m mypy app/core/model_config_store.py app/core/config.py app/api/settings_model.py --ignore-missing-imports`
Expected: no errors (or only pre-existing)

- [ ] **Step 6.4: tsc on frontend**

Run: `cd frontend && npx tsc --noEmit`
Expected: no errors

- [ ] **Step 6.5: Manual smoke test (verify skill)**

启动后端 + 前端，手动跑一遍：
1. 打开 `/settings/models`，确认看到三个 provider 卡 + source badge
2. 把 deepseek 模型改为 `deepseek-reasoner`，点击保存 → 看到 toast + source badge 变 `JSON 覆盖`
3. 触发一次诊断请求（确认后端真用了新模型）：`curl POST /api/diagnosis`，看日志 `model=deepseek-reasoner`
4. 重启后端，再 GET `/api/settings/models` → 仍是新值
5. 点击重置 → 二次确认 → source badge 变回 `环境变量`
6. 重启后端，再 GET → 退回 .env baseline

- [ ] **Step 6.6: Final commit**

```bash
git status
# 如有未跟踪改动 → 单独 commit
```

---

## Self-Review Checklist (run before declaring done)

- [ ] Spec coverage：spec §4-7 每一节都有对应 task 覆盖
- [ ] Placeholder scan：grep -E "TBD|TODO|implement later|fill in" plans file → 0 hit
- [ ] Type consistency：Task 3 DTO 字段 = Task 4 settingsApi 类型 = Task 5 表单 state shape
- [ ] Test count：spec §7.1-7.5 总计 49 用例，全部 1-to-1 在 plan 中体现
- [ ] 提交粒度：6 个 commit，每 commit 独立可运行
- [ ] 回归覆盖：spec §7.6 列出的 4 个现有测试在 Step 6.1 中已包含