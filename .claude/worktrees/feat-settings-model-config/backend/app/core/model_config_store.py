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
from dataclasses import dataclass
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
                loaded = self._load_from_disk()
                if loaded is not None:
                    loaded = self._verify_cipher_or_drop(loaded)
                self._cache = loaded  # None when file missing/corrupted
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