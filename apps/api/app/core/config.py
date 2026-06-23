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
    enable_bestbuy_scraping: bool = False
    adapter_timeout_seconds: int = 60
    playwright_headless: bool = True
    default_user_email: str = "demo@novaion.ai"
    geocoding_provider: str = "census"
    nominatim_user_agent: str = "NOVAIONSiteHunterLocal/1.2"
    nominatim_email: str | None = None
    overpass_api_url: str = "https://overpass-api.de/api/interpreter"
    power_asset_search_radii_miles: str = "1,3,5,10"
    transmission_line_geojson_path: str | None = None

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    @property
    def cors_origins(self) -> list[str]:
        return [origin.strip() for origin in self.api_cors_origins.split(",") if origin.strip()]

    @property
    def power_search_radii(self) -> list[float]:
        radii: list[float] = []
        for item in self.power_asset_search_radii_miles.split(","):
            try:
                radii.append(float(item.strip()))
            except ValueError:
                continue
        return radii or [1, 3, 5, 10]


@lru_cache
def get_settings() -> Settings:
    return Settings()
