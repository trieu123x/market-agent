from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.rag.retriever import RetrievedChunk


async def rerank(query: str, chunks: "list[RetrievedChunk]", top_k: int = 4) -> "list[RetrievedChunk]":
    """Stub: giữ nguyên thứ tự RRF. Thay bằng cross-encoder khi có thời gian (buffer ngày 5)."""
    return chunks[:top_k]
