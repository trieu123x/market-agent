import logging
import uuid

from app.agent.state import AgentState, RagSource
from app.db.session import SessionLocal
from app.rag.retriever import RetrievedChunk, retrieve

logger = logging.getLogger(__name__)


def _format_chunk(i: int, chunk: RetrievedChunk) -> str:
    return f"[{i}] {chunk.document_title} (đoạn {chunk.chunk_index})\n{chunk.content}"


def _source(i: int, chunk: RetrievedChunk) -> RagSource:
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
    )


async def intent_rag(state: AgentState) -> dict:
    """Truy xuất tài liệu theo brief (kèm phản hồi reject nếu có). Lỗi RAG không chặn luồng, chỉ bỏ context."""
    query = state["campaign_topic"]
    if feedback := state.get("outline_feedback"):
        query = f"{query}\n{feedback}"
    try:
        async with SessionLocal() as session:
            chunks = await retrieve(session, query, uuid.UUID(state["user_id"]))
    except Exception:
        logger.exception("RAG retrieval failed for thread=%s", state.get("thread_id"))
        chunks = []
    numbered = list(enumerate(chunks, start=1))
    return {
        "retrieved_rag_context": [_format_chunk(i, c) for i, c in numbered],
        "retrieved_sources": [_source(i, c) for i, c in numbered],
    }
