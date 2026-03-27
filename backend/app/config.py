"""Configuration management using Pydantic Settings."""

from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Application
    app_name: str = "ScrapeRL"
    app_version: str = "0.1.0"
    debug: bool = Field(default=False, description="Enable debug mode")
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"

    # Server
    host: str = "0.0.0.0"
    port: int = 8000
    reload: bool = False
    workers: int = 1

    # CORS
    cors_origins: list[str] = Field(
        default=["http://localhost:3000", "http://localhost:5173"],
        description="Allowed CORS origins",
    )
    cors_allow_credentials: bool = True
    cors_allow_methods: list[str] = ["*"]
    cors_allow_headers: list[str] = ["*"]

    # LLM Providers
    openai_api_key: SecretStr | None = Field(default=None, description="OpenAI API key")
    anthropic_api_key: SecretStr | None = Field(default=None, description="Anthropic API key")
    google_api_key: SecretStr | None = Field(default=None, description="Google AI API key")
    groq_api_key: SecretStr | None = Field(default=None, description="Groq API key")

    # Model Defaults
    default_model: str = "gpt-4o-mini"
    default_temperature: float = 0.7
    max_tokens: int = 4096

    # Search Providers
    google_search_api_key: SecretStr | None = None
    google_search_engine_id: str | None = None
    bing_search_api_key: SecretStr | None = None

    # ChromaDB
    chroma_persist_directory: str = "./data/chroma"
    chroma_collection_name: str = "scraperl_memory"

    # Episode Settings
    max_steps_per_episode: int = 50
    default_timeout_seconds: float = 30.0

    # Browser Settings
    headless_browser: bool = True
    browser_timeout_ms: int = 30000

    # Memory Settings
    short_term_memory_size: int = 100
    working_memory_size: int = 20
    long_term_memory_top_k: int = 10

    # Reward Weights
    reward_accuracy_weight: float = 0.4
    reward_efficiency_weight: float = 0.2
    reward_cost_weight: float = 0.2
    reward_completeness_weight: float = 0.2

    @property
    def available_providers(self) -> list[str]:
        """Return list of configured LLM providers."""
        providers = []
        if self.openai_api_key:
            providers.append("openai")
        if self.anthropic_api_key:
            providers.append("anthropic")
        if self.google_api_key:
            providers.append("google")
        if self.groq_api_key:
            providers.append("groq")
        return providers


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
