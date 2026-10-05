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
    """Điều kiện quyền: doc READY và (SYSTEM hoặc PRIVATE của user)."""
    return and_(
        Document.processing_status == "READY",
        or_(Document.scope == "SYSTEM", and_(Document.scope == "PRIVATE", Document.user_id == user_id)),
    )


def _phrase_tsquery(query: str) -> str:
    """Tiếng Việt: một từ thường gồm nhiều âm tiết ("nghỉ việc", "trả lương"); khớp từng âm tiết rời làm
    chunk chứa âm tiết phổ biến lấn át. Vì vậy OR các cặp âm tiết liền nhau (`a <-> b`)."""
    tokens = re.findall(r"\w+", query.lower())
    if len(tokens) == 1:
        return tokens[0]
    return " | ".join(dict.fromkeys(f"{a} <-> {b}" for a, b in zip(tokens, tokens[1:])))


def _word_tsquery(query: str) -> str:
    """Dự phòng khi không cặp nào khớp (vd. mã sản phẩm, tên riêng): OR từng từ."""
    return " | ".join(dict.fromkeys(w for w in re.findall(r"\w+", query.lower()) if len(w) > 1))


def _columns():
    """Các cột cần lấy cho một chunk kết quả."""
    return (
        DocumentChunk.id,
        DocumentChunk.document_id,
        Document.title,
        DocumentChunk.chunk_index,
        DocumentChunk.content,
        DocumentChunk.metadata_,
    )


def _to_chunk(row) -> RetrievedChunk:
    """Chuyển một row DB thành RetrievedChunk."""
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
    """Tìm theo độ tương đồng vector (cosine, HNSW)."""
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
    """Tìm full-text: thử cụm âm tiết liền nhau trước, không có thì OR từng từ."""
    for tsquery_text in dict.fromkeys((_phrase_tsquery(query), _word_tsquery(query))):
        if tsquery_text and (hits := await _fulltext_query(session, tsquery_text, user_id, limit)):
            return hits
    return []


async def _fulltext_query(session: AsyncSession, tsquery_text: str, user_id: uuid.UUID, limit: int):
    """Chạy một truy vấn tsquery và xếp hạng theo ts_rank_cd."""
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
    """Gộp nhiều danh sách xếp hạng thành một bằng điểm RRF."""
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
    """Tìm vector + full-text rồi gộp bằng RRF, lấy top_n."""
    qvec = await get_embedder().embed_query(query)
    vector_hits = await _vector_search(session, qvec, user_id, CANDIDATES_PER_SOURCE)
    fts_hits = await _fulltext_search(session, query, user_id, CANDIDATES_PER_SOURCE)
    return reciprocal_rank_fusion({"vector": vector_hits, "fts": fts_hits})[:top_n]


async def retrieve(
    session: AsyncSession, query: str, user_id: uuid.UUID, top_k: int = FINAL_TOP_K
) -> list[RetrievedChunk]:
    """Hàm retrieval chính: hybrid search rồi rerank, trả top_k chunk."""
    candidates = await hybrid_search(session, query, user_id)
    return await rerank(query, candidates, top_k)
