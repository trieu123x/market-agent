import asyncio
import logging
import uuid
from itertools import zip_longest

from app.agent.state import AgentState, RagSource
from app.core.config import get_settings
from app.db.session import SessionLocal
from app.rag.retriever import FINAL_TOP_K, RetrievedChunk, retrieve

logger = logging.getLogger(__name__)

RAG_QUERY_ATTACHMENT_CHARS = 500
BRIEF_NEED = "Brief chiến dịch"
PER_NEED_TOP_K = 3
MAX_CONTEXT_CHUNKS = 12


def _format_chunk(i: int, chunk: RetrievedChunk, needs: list[str]) -> str:
    return f"[{i}] {chunk.document_title} (đoạn {chunk.chunk_index}) · phục vụ: {'; '.join(needs)}\n{chunk.content}"


def _source(i: int, chunk: RetrievedChunk, needs: list[str]) -> RagSource:
    return RagSource(
        ref=i,
        chunk_id=str(chunk.chunk_id),
        document_id=str(chunk.document_id),
        document_title=chunk.document_title,
        chunk_index=chunk.chunk_index,
        headings=list(chunk.metadata.get("headings") or []),
        content=chunk.content,
        score=round(chunk.score, 6),
        ranks=dict(chunk.ranks),
        needs=needs,
    )


def _brief_query(state: AgentState) -> str:
    # Kèm phần đầu tệp đính kèm (vd. mô tả ảnh) để brief kiểu "viết về sản phẩm trong ảnh" vẫn tra được tài liệu
    parts = [state["campaign_topic"], *(a[:RAG_QUERY_ATTACHMENT_CHARS] for a in state.get("attachment_context", []))]
    if feedback := state.get("outline_feedback"):
        parts.append(feedback)
    return "\n".join(parts)


async def _retrieve(query: str, user_id: uuid.UUID, top_k: int, thread_id: str | None) -> list[RetrievedChunk]:
    """Mỗi truy vấn một session để chạy song song; lỗi chỉ làm mất kết quả của truy vấn đó."""
    try:
        async with SessionLocal() as session:
            return await retrieve(session, query, user_id, top_k)
    except Exception:
        logger.exception("RAG retrieval failed for thread=%s query=%r", thread_id, query[:80])
        return []


def drop_irrelevant(chunks: list[RetrievedChunk], min_score: float) -> list[RetrievedChunk]:
    """Bỏ chunk Cross-Encoder chấm dưới ngưỡng để nhu cầu không có tài liệu khớp không bị nhét chunk lạc đề;
    chunk chưa rerank (reranker tắt/lỗi) giữ nguyên."""
    return [c for c in chunks if c.rerank_score is None or c.rerank_score >= min_score]


def merge_results(results: list[tuple[str, list[RetrievedChunk]]], limit: int) -> list[tuple[RetrievedChunk, list[str]]]:
    """Gộp kết quả nhiều truy vấn theo vòng (hạng 1 của mọi truy vấn, rồi hạng 2...) để nhu cầu nào cũng có chỗ;
    chunk trùng giữ một bản, ghi thêm tên nhu cầu."""
    merged: dict[uuid.UUID, tuple[RetrievedChunk, list[str]]] = {}
    for tier in zip_longest(*[[(name, c) for c in chunks] for name, chunks in results]):
        for name, chunk in filter(None, tier):
            if chunk.chunk_id in merged:
                if name not in (needs := merged[chunk.chunk_id][1]):
                    needs.append(name)
            elif len(merged) < limit:
                merged[chunk.chunk_id] = (chunk, [name])
    return list(merged.values())


async def intent_rag(state: AgentState) -> dict:
    """Truy xuất tài liệu theo brief + từng kỹ năng/kiến thức trong knowledge_plan (song song).
    Lỗi RAG không chặn luồng, chỉ bỏ context."""
    queries = [(BRIEF_NEED, _brief_query(state), FINAL_TOP_K)]
    queries += [(n["name"], n["query"], PER_NEED_TOP_K) for n in state.get("knowledge_plan", [])]
    user_id, thread_id = uuid.UUID(state["user_id"]), state.get("thread_id")
    hits = await asyncio.gather(*(_retrieve(q, user_id, k, thread_id) for _, q, k in queries))
    min_score = get_settings().reranker_min_score
    results = [(name, drop_irrelevant(h, min_score)) for (name, _, _), h in zip(queries, hits)]
    numbered = list(enumerate(merge_results(results, MAX_CONTEXT_CHUNKS), start=1))
    return {
        "retrieved_rag_context": [_format_chunk(i, c, needs) for i, (c, needs) in numbered],
        "retrieved_sources": [_source(i, c, needs) for i, (c, needs) in numbered],
    }
