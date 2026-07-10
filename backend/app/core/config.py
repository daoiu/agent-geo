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
    llm_call_timeout_s: int = 30
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

    @property
    def enabled_providers(self) -> list[str]:
        """Parse llm_providers into list."""
        return [p.strip() for p in self.llm_providers.split(",") if p.strip()]

    @model_validator(mode="after")
    def _require_deepseek_api_key(self) -> "Settings":
        """Fail loudly at startup if no LLM key is configured.

        Prevents the silent fallback that produced the
        ``Authorization: Bearer `` Illegal header bug. Tests can opt out
        by exporting ``GEO_ALLOW_MISSING_LLM_KEY=1`` so they don't need
        a real key on disk.
        """
        if self.deepseek_api_key:
            return self
        if os.environ.get("GEO_ALLOW_MISSING_LLM_KEY") == "1":
            return self
        env_path = _PROJECT_ENV_FILE
        raise ValueError(
            "DEEPSEEK_API_KEY is empty. Populate "
            f"{env_path} (or set the DEEPSEEK_API_KEY env var). "
            "For unit tests that don't exercise the LLM call, set "
            "GEO_ALLOW_MISSING_LLM_KEY=1."
        )


@lru_cache
def get_settings() -> Settings:
    """Cached settings singleton."""
    return Settings()
