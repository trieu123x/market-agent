"""Hybrid retrieval: dense (pgvector cosine) + sparse (Postgres FTS) → Reciprocal Rank Fusion.

Quyền truy cập: scope = 'SYSTEM' OR (scope = 'PRIVATE' AND user_id = current_user).
"""
import re
import uuid
from dataclasses import dataclass, field

from sqlalchemy import and_, func, or_, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Document, DocumentChunk
from app.rag.embedder import get_embedder
from app.rag.reranker import rerank

RRF_K = 60
CANDIDATES_PER_SOURCE = 30
FUSED_TOP_N = 15
FINAL_TOP_K = 4


@dataclass
class RetrievedChunk:
    chunk_id: uuid.UUID
    document_id: uuid.UUID
    document_title: str
    chunk_index: int
    content: str
    metadata: dict
    score: float = 0.0
    ranks: dict[str, int] = field(default_factory=dict)


def _scope_filter(user_id: uuid.UUID):
    return and_(
        Document.processing_status == "READY",
        or_(Document.scope == "SYSTEM", and_(Document.scope == "PRIVATE", Document.user_id == user_id)),
    )


def _to_tsquery_text(query: str) -> str:
    # OR các từ để câu hỏi dài vẫn match; ts_rank_cd ưu tiên chunk khớp nhiều từ hơn.
    words = dict.fromkeys(w for w in re.findall(r"\w+", query.lower()) if len(w) > 1)
    return " | ".join(words)


def _columns():
    return (
        DocumentChunk.id,
        DocumentChunk.document_id,
        Document.title,
        DocumentChunk.chunk_index,
        DocumentChunk.content,
        DocumentChunk.metadata_,
    )


def _to_chunk(row) -> RetrievedChunk:
    return RetrievedChunk(
        chunk_id=row.id,
        document_id=row.document_id,
        document_title=row.title,
        chunk_index=row.chunk_index,
        content=row.content,
        metadata=row.metadata_ or {},
    )


async def _vector_search(session: AsyncSession, qvec: list[float], user_id: uuid.UUID, limit: int):
    # Lọc scope sau HNSW có thể làm hụt kết quả → bật iterative scan (pgvector >= 0.8).
    await session.execute(text("SET LOCAL hnsw.iterative_scan = relaxed_order"))
    distance = DocumentChunk.embedding.cosine_distance(qvec)
    stmt = (
        select(*_columns())
        .join(Document, Document.id == DocumentChunk.document_id)
        .where(_scope_filter(user_id))
        .order_by(distance)
        .limit(limit)
    )
    return [_to_chunk(r) for r in (await session.execute(stmt)).all()]


async def _fulltext_search(session: AsyncSession, query: str, user_id: uuid.UUID, limit: int):
    tsquery_text = _to_tsquery_text(query)
    if not tsquery_text:
        return []
    tsq = func.to_tsquery("simple", tsquery_text)
    tsv = func.to_tsvector("simple", DocumentChunk.content)  # khớp biểu thức của GIN index
    rank = func.ts_rank_cd(tsv, tsq)
    stmt = (
        select(*_columns())
        .join(Document, Document.id == DocumentChunk.document_id)
        .where(_scope_filter(user_id), tsv.op("@@")(tsq))
        .order_by(rank.desc())
        .limit(limit)
    )
    return [_to_chunk(r) for r in (await session.execute(stmt)).all()]


def reciprocal_rank_fusion(ranked_lists: dict[str, list[RetrievedChunk]], k: int = RRF_K) -> list[RetrievedChunk]:
    fused: dict[uuid.UUID, RetrievedChunk] = {}
    for source, chunks in ranked_lists.items():
        for rank, chunk in enumerate(chunks, start=1):
            item = fused.setdefault(chunk.chunk_id, chunk)
            item.score += 1.0 / (k + rank)
            item.ranks[source] = rank
    return sorted(fused.values(), key=lambda c: c.score, reverse=True)


async def hybrid_search(
    session: AsyncSession, query: str, user_id: uuid.UUID, top_n: int = FUSED_TOP_N
) -> list[RetrievedChunk]:
    [qvec] = await get_embedder().embed([query])
    vector_hits = await _vector_search(session, qvec, user_id, CANDIDATES_PER_SOURCE)
    fts_hits = await _fulltext_search(session, query, user_id, CANDIDATES_PER_SOURCE)
    return reciprocal_rank_fusion({"vector": vector_hits, "fts": fts_hits})[:top_n]


async def retrieve(
    session: AsyncSession, query: str, user_id: uuid.UUID, top_k: int = FINAL_TOP_K
) -> list[RetrievedChunk]:
    candidates = await hybrid_search(session, query, user_id)
    return await rerank(query, candidates, top_k)
