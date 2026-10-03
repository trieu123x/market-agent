import os
import tempfile
import uuid

# Test chạy không cần Redis / OpenAI: task chạy in-process, embedding giả lập.
os.environ.setdefault("TASK_BROKER", "memory")
os.environ.setdefault("EMBEDDING_PROVIDER", "hash")
os.environ.setdefault("UPLOAD_DIR", os.path.join(tempfile.gettempdir(), "market_agent_test_uploads"))

import pytest  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402

from app.db.session import engine  # noqa: E402
from app.main import app  # noqa: E402


@pytest.fixture(autouse=True)
async def _dispose_engine_pool():
    yield
    await engine.dispose()


@pytest.fixture
async def client():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


@pytest.fixture
def unique_email() -> str:
    return f"user-{uuid.uuid4().hex[:8]}@example.com"
