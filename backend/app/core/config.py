from functools import lru_cache
from typing import Literal

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

    # "redis": API đẩy task vào Redis, cần chạy `taskiq worker`.
    # "memory": task chạy ngay trong process API (dev/test, không cần Redis).
    task_broker: Literal["redis", "memory"] = "redis"

    upload_dir: str = "storage/uploads"
    max_upload_bytes: int = 10 * 1024 * 1024
    url_fetch_timeout_seconds: float = 15.0

    # "auto": dùng OpenAI nếu có OPENAI_API_KEY, ngược lại dùng hash embedder (chỉ cho dev/test).
    embedding_provider: Literal["auto", "openai", "hash"] = "auto"
    embedding_model: str = "text-embedding-3-small"
    embedding_batch_size: int = 64

    chunk_tokens: int = 800
    chunk_overlap_tokens: int = 150


@lru_cache
def get_settings() -> Settings:
    return Settings()
