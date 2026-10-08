from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "Marketing Agent"
    debug: bool = False
    log_level: str = "INFO"

    # Origin của frontend được gọi API trực tiếp (CORS). Env: CORS_ORIGINS='["http://localhost:3010"]'
    cors_origins: list[str] = ["http://localhost:3010"]

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

    # Gemini embedding (dùng GOOGLE_API_KEY), cắt về 1536 chiều.
    embedding_model: str = "gemini-embedding-001"
    embedding_batch_size: int = 64

    # Cross-Encoder rerank top 15 RRF → top 8 (sentence-transformers, CPU). Model đa ngôn ngữ, có tiếng Việt.
    reranker_enabled: bool = True
    reranker_model: str = "cross-encoder/mmarco-mMiniLMv2-L12-H384-v1"
    reranker_max_length: int = 512
    # Ngưỡng điểm Cross-Encoder để chunk được đưa vào context agent. Model trên trả logit thô:
    # đoạn liên quan ~ -2..+5, không liên quan ~ -8. Đổi model thì phải chỉnh lại.
    reranker_min_score: float = -5.0

    # Gemini phân tích ảnh đính kèm khi chat (dùng GOOGLE_API_KEY)
    vision_model: str = "gemini-2.5-flash"

    chunk_tokens: int = 800
    chunk_overlap_tokens: int = 150

    # OCR cho ảnh nhúng trong PDF (PyMuPDF + Tesseract, cần cài `tesseract-ocr` + tessdata).
    ocr_enabled: bool = True
    ocr_language: str = "vie+eng"
    ocr_dpi: int = 200
    ocr_min_image_px: int = 100  # bỏ qua icon/logo nhỏ hơn ngưỡng này (cạnh ngắn nhất)

    # Rate limit chat/resume theo user. "memory" chỉ dùng cho dev/test một process.
    rate_limit_per_minute: int = 30
    rate_limit_backend: Literal["redis", "memory"] = "redis"

    llm_temperature: float = 0.7
    llm_max_tokens: int = 4096


@lru_cache
def get_settings() -> Settings:
    return Settings()
