from __future__ import annotations
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")
    openai_api_key: str

    amadeus_api_key: str | None = None
    amadeus_api_secret: str | None = None
    geoapify_api_key: str | None = None

    apify_token: str | None = None
    enable_apify: bool = False

    default_currency: str = "USD"
    agent_model: str = "gpt-4o-mini"
    request_timeout: float = 20.0
    contact_email: str = "you@example.com"
    session_store_dir: str = ".sessions"

    @property
    def amadues_ready(self) -> bool:
        return bool(self.amadeus_api_key and self.amadeus_api_secret)

    @property
    def apify_ready(self) -> bool:
        return bool(self.apify_token and self.enable_apify)

@lru_cache()
def get_settings() -> Settings:
    return Settings()


if __name__ == "__main__":
    s = get_settings()
    print(s.dict())
