from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "Marketing Agent"
    debug: bool = False
    log_level: str = "INFO"

    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5434/market_agent_db"
    redis_url: str = "redis://localhost:6380/0"

    jwt_secret: str = "change-me"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60

    admin_email: str = "admin@example.com"
    admin_password: str = "admin12345"

    openai_api_key: str = ""
    anthropic_api_key: str = ""
    google_api_key: str = ""


@lru_cache
def get_settings() -> Settings:
    return Settings()
