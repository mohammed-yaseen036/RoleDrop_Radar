from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_env: str = "development"
    app_secret_key: str = "development-only-change-me"
    database_url: str = "sqlite:///./role_drop_radar.db"
    frontend_url: str = "http://localhost:5173"

    supabase_url: str | None = None
    supabase_anon_key: str | None = None

    gemini_api_key: str | None = None
    gemini_model: str = "gemini-2.5-flash-lite"
    enable_ollama: bool = False
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama3:latest"

    telegram_bot_token: str | None = None
    telegram_bot_username: str | None = None
    telegram_webhook_secret: str | None = None
    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 587
    smtp_username: str | None = None
    smtp_password: str | None = None
    smtp_from: str | None = None
    smtp_use_tls: bool = True

    monitor_api_key: str | None = None
    alert_score_threshold: int = Field(default=75, ge=0, le=100)

    model_config = SettingsConfigDict(
        env_file=("../.env", ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def is_development(self) -> bool:
        return self.app_env.lower() in {"development", "test"}

    @property
    def supabase_auth_enabled(self) -> bool:
        return bool(self.supabase_url and self.supabase_anon_key)


@lru_cache
def get_settings() -> Settings:
    return Settings()
