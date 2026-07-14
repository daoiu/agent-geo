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

    @property
    def enabled_providers(self) -> list[str]:
        """Parse llm_providers into list."""
        return [p.strip() for p in self.llm_providers.split(",") if p.strip()]

    @property
    def parsed_fallback_chain(self) -> list[str]:
        """Parse fallback_chain into list of provider names."""
        return [p.strip() for p in self.fallback_chain.split(",") if p.strip()]

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
    """Cached settings singleton."""
    return Settings()
