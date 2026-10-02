import uuid

import pytest
from httpx import ASGITransport, AsyncClient

from app.db.session import engine
from app.main import app


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
