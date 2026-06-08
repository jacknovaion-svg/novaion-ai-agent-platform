from __future__ import annotations

from functools import lru_cache

from pydantic import AnyHttpUrl
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "NOVAION AI Agent Platform"
    app_env: str = "development"
    api_cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000"
    database_url: str | None = None
    enable_live_scraping: bool = False
    adapter_timeout_seconds: int = 60
    playwright_headless: bool = True
    default_user_email: str = "demo@novaion.ai"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    @property
    def cors_origins(self) -> list[str]:
        return [origin.strip() for origin in self.api_cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
