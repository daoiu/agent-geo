"""Application configuration loaded from environment variables."""
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """App settings (env-driven)."""

    model_config = SettingsConfigDict(
        env_file=".env",
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

    @property
    def enabled_providers(self) -> list[str]:
        """Parse llm_providers into list."""
        return [p.strip() for p in self.llm_providers.split(",") if p.strip()]


@lru_cache
def get_settings() -> Settings:
    """Cached settings singleton."""
    return Settings()
