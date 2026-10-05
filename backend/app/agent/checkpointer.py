"""AsyncPostgresSaver (psycopg) dùng chung Postgres với app; bảng checkpoint do `setup()` tự tạo."""
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from psycopg.rows import dict_row
from psycopg_pool import AsyncConnectionPool

from app.core.config import get_settings


def _conninfo() -> str:
    # DATABASE_URL của SQLAlchemy dạng postgresql+asyncpg://… → psycopg cần postgresql://…
    return get_settings().database_url.replace("postgresql+asyncpg://", "postgresql://", 1)


async def open_checkpointer() -> tuple[AsyncPostgresSaver, AsyncConnectionPool]:
    """Gọi lúc startup, không gọi lần đầu trong request: `setup()` có CREATE INDEX CONCURRENTLY, lệnh này
    chờ mọi transaction đang mở – kể cả transaction SQLAlchemy của chính request đó → treo vĩnh viễn."""
    pool = AsyncConnectionPool(
        _conninfo(),
        max_size=10,
        open=False,
        kwargs={"autocommit": True, "prepare_threshold": 0, "row_factory": dict_row},
    )
    await pool.open()
    saver = AsyncPostgresSaver(pool)
    await saver.setup()
    return saver, pool
