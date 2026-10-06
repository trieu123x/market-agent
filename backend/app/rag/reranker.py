"""Rerank ứng viên RRF bằng Cross-Encoder (sentence-transformers), chạy local trên CPU.

Model nạp lười ở lần gọi đầu (tải từ HuggingFace về HF_HOME). Lỗi model không chặn retrieval:
log cảnh báo rồi giữ nguyên thứ tự RRF.
"""
import asyncio
import logging
from functools import lru_cache
from typing import TYPE_CHECKING

from app.core.config import get_settings

if TYPE_CHECKING:
    from sentence_transformers import CrossEncoder

    from app.rag.retriever import RetrievedChunk

logger = logging.getLogger(__name__)


@lru_cache
def get_cross_encoder() -> "CrossEncoder":
    """Nạp Cross-Encoder một lần cho cả process (import torch chậm nên để trong hàm)."""
    from sentence_transformers import CrossEncoder

    settings = get_settings()
    return CrossEncoder(settings.reranker_model, max_length=settings.reranker_max_length, device="cpu")


def _score(query: str, contents: list[str]) -> list[float]:
    """Chấm điểm liên quan (query, chunk) theo batch; chạy đồng bộ nên gọi qua thread."""
    scores = get_cross_encoder().predict([(query, c) for c in contents], batch_size=len(contents))
    return [float(s) for s in scores]


async def warmup() -> None:
    """Nạp model trước (gọi lúc startup) để query đầu tiên không phải chờ tải model."""
    try:
        await asyncio.to_thread(_score, "warmup", ["warmup"])
    except Exception:
        logger.exception("Reranker warmup failed (model=%s)", get_settings().reranker_model)


async def rerank(query: str, chunks: "list[RetrievedChunk]", top_k: int = 4) -> "list[RetrievedChunk]":
    """Sắp lại chunk theo điểm Cross-Encoder, trả top_k. Tắt reranker hoặc lỗi → giữ thứ tự RRF."""
    if not chunks or not get_settings().reranker_enabled:
        return chunks[:top_k]
    try:
        scores = await asyncio.to_thread(_score, query, [c.content for c in chunks])
    except Exception:
        logger.exception("Rerank failed, falling back to RRF order")
        return chunks[:top_k]
    for chunk, score in zip(chunks, scores):
        chunk.rerank_score = score
    return sorted(chunks, key=lambda c: c.rerank_score, reverse=True)[:top_k]
