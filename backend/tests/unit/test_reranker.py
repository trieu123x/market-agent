import uuid

import pytest

from app.core.config import get_settings
from app.rag import reranker
from app.rag.retriever import RetrievedChunk


def _chunk(content: str) -> RetrievedChunk:
    return RetrievedChunk(uuid.uuid4(), uuid.uuid4(), "t", 0, content, {})


class FakeCrossEncoder:
    """Điểm = số từ của query xuất hiện trong chunk."""

    def predict(self, pairs, batch_size=32):
        return [sum(w in c.split() for w in q.split()) for q, c in pairs]


@pytest.fixture
def enabled(monkeypatch):
    monkeypatch.setattr(get_settings(), "reranker_enabled", True)


async def test_rerank_orders_by_cross_encoder_score(monkeypatch, enabled):
    monkeypatch.setattr(reranker, "get_cross_encoder", lambda: FakeCrossEncoder())
    chunks = [_chunk("giá xăng"), _chunk("chính sách nghỉ việc trả lương"), _chunk("nghỉ phép")]
    top = await reranker.rerank("nghỉ việc trả lương", chunks, top_k=2)
    assert [c.content for c in top] == ["chính sách nghỉ việc trả lương", "nghỉ phép"]
    assert [c.rerank_score for c in top] == [4.0, 1.0]


async def test_rerank_falls_back_to_rrf_order_on_error(monkeypatch, enabled):
    def broken():
        raise RuntimeError("model download failed")

    monkeypatch.setattr(reranker, "get_cross_encoder", broken)
    chunks = [_chunk("a"), _chunk("b"), _chunk("c")]
    assert await reranker.rerank("b", chunks, top_k=2) == chunks[:2]
    assert all(c.rerank_score is None for c in chunks)


async def test_rerank_disabled_keeps_rrf_order(monkeypatch):
    monkeypatch.setattr(get_settings(), "reranker_enabled", False)
    monkeypatch.setattr(reranker, "get_cross_encoder", lambda: pytest.fail("model must not load"))
    chunks = [_chunk("a"), _chunk("b")]
    assert await reranker.rerank("b", chunks, top_k=1) == chunks[:1]
