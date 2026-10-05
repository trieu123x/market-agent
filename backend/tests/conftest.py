import hashlib
import math
import os
import re
import tempfile
import uuid

# Test chạy không cần Redis: task chạy in-process.
os.environ.setdefault("TASK_BROKER", "memory")
os.environ.setdefault("UPLOAD_DIR", os.path.join(tempfile.gettempdir(), "market_agent_test_uploads"))

import pytest  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402
from sqlalchemy import text  # noqa: E402

from app.db.models.document import EMBEDDING_DIM  # noqa: E402
from app.db.session import engine  # noqa: E402
from app.main import app  # noqa: E402


class FakeEmbedder:
    """Embedding offline cho test (feature hashing trên từ): không gọi Gemini, khớp theo từ vựng."""

    name = "test-fake"

    def _vector(self, text_: str) -> list[float]:
        vec = [0.0] * EMBEDDING_DIM
        for word in re.findall(r"\w+", text_.lower()):
            h = int.from_bytes(hashlib.blake2b(word.encode(), digest_size=8).digest(), "big")
            vec[h % EMBEDDING_DIM] += 1.0 if (h >> 63) & 1 else -1.0
        norm = math.sqrt(sum(v * v for v in vec)) or 1.0
        return [v / norm for v in vec] if any(vec) else [1.0] + [0.0] * (EMBEDDING_DIM - 1)

    async def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self._vector(t) for t in texts]

    async def embed_query(self, text_: str) -> list[float]:
        return self._vector(text_)


@pytest.fixture(autouse=True)
def _fake_embedder(monkeypatch):
    fake = FakeEmbedder()
    monkeypatch.setattr("app.rag.retriever.get_embedder", lambda: fake)
    monkeypatch.setattr("app.services.document_service.get_embedder", lambda: fake)


@pytest.fixture(scope="session", autouse=True)
async def _cleanup_test_data():
    """Xóa dữ liệu test khỏi DB dev sau khi chạy xong (tài liệu embed bằng FakeEmbedder + user test)."""
    yield
    async with engine.begin() as conn:
        await conn.execute(
            text(
                "DELETE FROM documents WHERE id IN "
                "(SELECT document_id FROM document_chunks WHERE metadata->>'embedding_model' = :m)"
            ),
            {"m": FakeEmbedder.name},
        )
        await conn.execute(text("DELETE FROM users WHERE email LIKE 'user-%@example.com'"))
    await engine.dispose()


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
