import hashlib
import math
import os
import re
import tempfile
import uuid

# Test chạy không cần Redis: task chạy in-process.
os.environ.setdefault("TASK_BROKER", "memory")
os.environ.setdefault("RATE_LIMIT_BACKEND", "memory")
os.environ.setdefault("RERANKER_ENABLED", "false")  # không tải model trong test; test reranker dùng model giả
os.environ.setdefault("UPLOAD_DIR", os.path.join(tempfile.gettempdir(), "market_agent_test_uploads"))

import json  # noqa: E402
from collections.abc import Callable  # noqa: E402

import pytest  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402
from langchain_core.language_models import BaseChatModel  # noqa: E402
from langchain_core.messages import AIMessage, AIMessageChunk, BaseMessage  # noqa: E402
from langchain_core.outputs import ChatGeneration, ChatGenerationChunk, ChatResult  # noqa: E402
from sqlalchemy import text  # noqa: E402

from app.agent.graph import close_graph, get_graph  # noqa: E402
from app.agent.nodes.multi_format_generator import PLATFORM_RULES  # noqa: E402
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


OUTLINE = "### Dàn ý chiến dịch: FinTech Launch\n1. **Mục tiêu** – tăng 20% lead\n2. **Đối tượng** – CFO SME"
DRAFTS = {
    "linkedin": "CFO SME mất 3 ngày mỗi tháng cho đối soát. PayNow rút còn 1 giờ. #fintech",
    "twitter": "1/ Đối soát thủ công tốn 3 ngày mỗi tháng.\n\n2/ PayNow làm việc đó trong 1 giờ.",
    "facebook": "Kế toán ơi, cuối tháng đừng thức khuya đối soát nữa! Đăng ký PayNow ngay hôm nay.",
}
CHECK_PASS = json.dumps({"passed": True, "summary": "Không phát hiện lỗi.", "issues": []})


def role_of(messages: list[BaseMessage]) -> str:
    """Nhận diện node đang gọi LLM qua system prompt (xem app/agent/prompts/*.md)."""
    system = messages[0].content
    if "biên tập lại" in system:  # trước "fact-checker": prompt refine cũng nhắc tới fact-checker
        return "refine"
    if "fact-checker" in system:
        return "fact_checker"
    if "copywriter" in system:
        return "generator"
    return "outline"


def platform_of(messages: list[BaseMessage]) -> str:
    return next(p for p, rule in PLATFORM_RULES.items() if rule in messages[-1].content)


def default_responder(messages: list[BaseMessage]) -> str:
    role = role_of(messages)
    if role == "fact_checker":
        return CHECK_PASS
    if role == "refine":
        return f"Bản {platform_of(messages)} đã sửa theo fact-check."
    if role == "generator":
        return DRAFTS[platform_of(messages)]
    return OUTLINE


class ScriptedLLM(BaseChatModel):
    """LLM giả: trả lời theo vai trò của node, stream từng từ, có usage_metadata (đếm từ) để test cost.
    Ghi lại mọi prompt đã nhận vào `prompts`."""

    responder: Callable[[list[BaseMessage]], str] = default_responder
    prompts: list = []

    @property
    def _llm_type(self) -> str:
        return "scripted-fake"

    def _reply(self, messages: list[BaseMessage]) -> tuple[str, dict]:
        self.prompts.append(messages)
        text_ = self.responder(messages)
        prompt_tokens = sum(len(str(m.content).split()) for m in messages)
        completion_tokens = len(text_.split())
        usage = {
            "input_tokens": prompt_tokens,
            "output_tokens": completion_tokens,
            "total_tokens": prompt_tokens + completion_tokens,
        }
        return text_, usage

    def _generate(self, messages, stop=None, run_manager=None, **kwargs) -> ChatResult:
        text_, usage = self._reply(messages)
        return ChatResult(generations=[ChatGeneration(message=AIMessage(text_, usage_metadata=usage))])

    def _stream(self, messages, stop=None, run_manager=None, **kwargs):
        text_, usage = self._reply(messages)
        for piece in re.findall(r"\S+\s*", text_):
            yield ChatGenerationChunk(message=AIMessageChunk(content=piece))
        yield ChatGenerationChunk(message=AIMessageChunk(content="", usage_metadata=usage))

    def calls(self, role: str) -> list[list[BaseMessage]]:
        return [m for m in self.prompts if role_of(m) == role]


@pytest.fixture
def fake_llm(monkeypatch):
    llm = ScriptedLLM()
    monkeypatch.setattr("app.agent.llm_factory.get_chat_model", lambda model_id: llm)
    return llm


@pytest.fixture(autouse=True)
def _fake_embedder(monkeypatch):
    fake = FakeEmbedder()
    monkeypatch.setattr("app.rag.retriever.get_embedder", lambda: fake)
    monkeypatch.setattr("app.services.document_service.get_embedder", lambda: fake)


@pytest.fixture(scope="session", autouse=True)
async def _cleanup_test_data():
    """Xóa dữ liệu test khỏi DB dev sau khi chạy xong (tài liệu embed bằng FakeEmbedder, user test,
    checkpoint của thread test – thread_id bắt đầu bằng "test-")."""
    await get_graph()  # ASGITransport không chạy lifespan → tự setup checkpointer như lúc startup
    yield
    await close_graph()
    async with engine.begin() as conn:
        if await conn.scalar(text("SELECT to_regclass('checkpoints') IS NOT NULL")):
            for table in ("checkpoint_writes", "checkpoint_blobs", "checkpoints"):
                await conn.execute(text(f"DELETE FROM {table} WHERE thread_id LIKE 'test-%'"))
        await conn.execute(
            text(
                "DELETE FROM documents WHERE id IN "
                "(SELECT document_id FROM document_chunks WHERE metadata->>'embedding_model' = :m)"
            ),
            {"m": FakeEmbedder.name},
        )
        await conn.execute(text("DELETE FROM model_pricing WHERE model_id LIKE '%-zztest-%'"))
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
