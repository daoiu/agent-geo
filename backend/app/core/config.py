"""Application configuration loaded from environment variables."""
from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Project root is anchored to backend/app/core/config.py → 3 parents up.
# This matches the convention used in docker-compose.yml (`env_file: .env`
# at repo root) and README's local-dev instructions
# (`cd backend && uvicorn app.main:app`).
_PROJECT_ROOT = Path(__file__).resolve().parents[3]
_PROJECT_ENV_FILE = _PROJECT_ROOT / ".env"


class Settings(BaseSettings):
    """App settings (env-driven)."""

    model_config = SettingsConfigDict(
        # Anchor to project root, NOT CWD. Running uvicorn from `backend/`
        # would otherwise miss `D:/GEO2/.env` and silently fall back to
        # defaults — observed as `Authorization: Bearer ` illegal header
        # once the empty key reached the OpenAI client.
        env_file=str(_PROJECT_ENV_FILE),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # DeepSeek
    deepseek_api_key: str = ""
    deepseek_base_url: str = "https://api.deepseek.com/v1"
    deepseek_model: str = "deepseek-chat"

    # Kimi
    kimi_api_key: str = ""
    kimi_base_url: str = "https://api.moonshot.cn/v1"
    kimi_model: str = "moonshot-v1-8k"

    # OpenAI
    openai_api_key: str = ""
    openai_base_url: str = "https://api.openai.com/v1"
    openai_model: str = "gpt-4o-mini"

    # LLM selection (comma-separated)
    llm_providers: str = "deepseek"

    # App
    app_port: int = 8000
    app_host: str = "0.0.0.0"
    database_url: str = "sqlite+aiosqlite:///./data/reports.db"
    log_level: str = "INFO"

    # Timeouts
    diagnosis_total_timeout_s: int = 90
    llm_call_timeout_s: int = 120  # v0.6 P1.5: MiniMax + 长 prompt + RAG chunks 30s 不够
    crawl_timeout_s: int = 10

    # Knowledge base / v0.2
    max_upload_size_mb: int = 50
    default_target_length: int = 1500
    chunk_min_length: int = 50
    chunk_max_length: int = 500
    retrieval_top_k: int = 5
    max_article_count_per_task: int = 20

    # v0.3 — encryption
    encryption_key: str = ""

    # v0.3 — SMTP
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_use_tls: bool = True
    smtp_from: str = ""

    # v0.3 — publish / monitor
    publish_timeout_s: int = 30
    monitor_change_threshold_default: float = 0.15
    notify_email_default: str = ""

    # v0.5 — Vector retrieval
    chroma_path: str = "./data/chroma"
    models_cache_dir: str = "./data/models"
    embedding_batch_size: int = 50
    hybrid_top_k_vector: int = 20
    hybrid_top_k_keyword: int = 20
    hybrid_rrf_k: int = 60

    # v0.6 P1.6 — L2 跨会话记忆
    memory_consolidate_threshold: int = 50  # 行数 ≥ 此值触发 consolidate
    # Phase 2 — 记忆层向量化
    memory_dedup_max_distance: float = 0.15  # cosine distance < 此值视为语义重复
    memory_extract_min_chars: int = 8         # 最近 user 文本短于此则跳过 extract
    # Phase 3 — 上下文预算
    context_window_messages: int = 40   # 送进 LLM 的最近历史条数上限
    tool_result_max_chars: int = 2000    # 旧 tool 结果截断字符上限
    tool_result_keep_recent: int = 3     # 最近 N 个 tool 结果保全量

    # v0.6+ P1#7 — Agent Loop 迭代上限（Task 8：从 react_loop.py 硬编码常量提到 Settings）
    max_react_iterations: int = 7        # 阶段 1 默认值,与原 MAX_REACT_ITERATIONS 一致

    # v0.6+ P1#11 — Token 级截断（Task 12）
    # tiktoken 编码名（cl100k_base = gpt-4/deepseek-chat 通用；o200k_base = gpt-4o）。
    # None 时回退到 tool_result_max_chars 字符级截断。
    tiktoken_encoding: str = "cl100k_base"
    token_budget_per_tool_result: int = 800  # 单条 tool 结果的 token 上限

    # v0.6+ P1#24 — 慢查询告警阈值（Task 25）
    llm_slow_query_threshold_ms: int = 60_000  # LLM 调用超过 60s 触发 warning

    # v0.6+ Multi-Agent 改造 — Handoff 协议配置（spec §3.4）
    handoff_timeout_content_writer: int = 300   # 秒
    handoff_timeout_monitor: int = 60            # 秒
    handoff_max_retries: int = 1                 # specialist 失败重试次数(不算超时)
    handoff_idempotency_window_hours: int = 24   # 幂等键有效期
    handoff_log_retention_days: int = 90         # handoff_log 表保留天数(自动清理待 P2 路线)

    # v0.6+ P1#25 — pending 超时自动取消（Task 26）
    pending_timeout_minutes: int = 5  # pending_confirmation 超 5 分钟自动取消

    # v0.7+ P2#50 — 自适应模型分级（Task 36）
    # 三档 provider 名:cheap(轻量任务) / standard(默认) / premium(关键决策)
    # 默认沿用 llm_providers 中的第一项,确保向后兼容。
    model_tier_cheap: str = "deepseek"
    model_tier_standard: str = "deepseek"
    model_tier_premium: str = "deepseek"

    # v0.7+ P2#51 — Fallback 链（Task 37）
    # 主 provider 失败切下一个。逗号分隔 provider 名。
    fallback_chain: str = "deepseek,kimi"

    # v0.8 — LangGraph 主循环开关（spec 2026-07-14-langgraph-react-loop §10.2）
    # 默认 False 沿用 react_loop.py，生产切流走 env LANGGRAPH_ENABLED=true
    langgraph_enabled: bool = False

    @property
    def enabled_providers(self) -> list[str]:
        """Parse llm_providers into list."""
        return [p.strip() for p in self.llm_providers.split(",") if p.strip()]

    @property
    def parsed_fallback_chain(self) -> list[str]:
        """Parse fallback_chain into list of provider names."""
        return [p.strip() for p in self.fallback_chain.split(",") if p.strip()]

    def merge_runtime_overrides(
        self,
        snapshot: "ModelConfigSnapshot | None",
    ) -> None:
        """把 JSON 快照合并进 self（仅 mutate 我们关心的字段）。

        规则（spec §4.2 / §5.1）：
        - 快照里没字段 → 不动 self（保留 .env baseline）
        - provider 名不在 PROVIDERS_META → 跳过 + warning
        - tier 值不在 PROVIDERS_META → 跳过该 tier + warning
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

        # provider name → Settings 字段名映射
        provider_field_map = {
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

        # providers → setattr
        for name, override in snapshot.providers.items():
            mapping = provider_field_map.get(name)
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
        tier_attr_map = {
            "cheap": "model_tier_cheap",
            "standard": "model_tier_standard",
            "premium": "model_tier_premium",
        }
        for tier_key, provider_name in snapshot.tiers.items():
            attr = tier_attr_map.get(tier_key)
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

    @model_validator(mode="after")
    def _require_some_api_key(self) -> "Settings":
        """Fail loudly at startup if no LLM key is configured at all.

        Plugins are now generic — any ``<NAME>_API_KEY`` env var works,
        not just ``DEEPSEEK_API_KEY``. We still enforce the legacy
        ``DEEPSEEK_*`` shortcut, and allow tests to bypass via
        ``GEO_ALLOW_MISSING_LLM_KEY=1``.
        """
        if os.environ.get("GEO_ALLOW_MISSING_LLM_KEY") == "1":
            return self
        import re as _re
        if self.deepseek_api_key:
            return self
        # Permit a non-DEEPSEEK provider to satisfy the requirement
        for key, val in os.environ.items():
            if _re.match(r"^[A-Z][A-Z0-9_]*_API_KEY$", key) and val:
                return self
        env_path = _PROJECT_ENV_FILE
        raise ValueError(
            "No LLM API key configured. Populate "
            f"{env_path} (e.g. `DEEPSEEK_API_KEY=...` or any "
            "`<NAME>_API_KEY=...` of your OpenAI-compatible provider). "
            "For unit tests that don't exercise the LLM call, set "
            "GEO_ALLOW_MISSING_LLM_KEY=1."
        )


@lru_cache
def get_settings() -> Settings:
    """Cached settings singleton (with runtime overrides merged)."""
    s = Settings()
    store = get_default_model_config_store()
    snapshot = store.load_snapshot()
    s.merge_runtime_overrides(snapshot)
    return s


_DEFAULT_MODEL_CONFIG_STORE: "ModelConfigStore | None" = None


def get_default_model_config_store() -> "ModelConfigStore":
    """获取默认 ModelConfigStore 单例（路径 data/model_config.json）。

    路径基于 cwd + data/：测试用 monkeypatch.chdir 切到 tmp_path 自动隔离。
    """
    global _DEFAULT_MODEL_CONFIG_STORE
    if _DEFAULT_MODEL_CONFIG_STORE is None:
        from app.core.model_config_store import ModelConfigStore

        settings_for_path = Settings()
        data_dir = Path.cwd() / "data"
        _DEFAULT_MODEL_CONFIG_STORE = ModelConfigStore(
            path=data_dir / "model_config.json",
            encryption_key=settings_for_path.encryption_key or "",
        )
    return _DEFAULT_MODEL_CONFIG_STORE


def reset_default_model_config_store() -> None:
    """测试用：清除单例。"""
    global _DEFAULT_MODEL_CONFIG_STORE
    _DEFAULT_MODEL_CONFIG_STORE = None
