import logging
import uuid

from app.agent.state import AgentState, RagSource
from app.db.session import SessionLocal
from app.rag.retriever import RetrievedChunk, retrieve

logger = logging.getLogger(__name__)

RAG_QUERY_ATTACHMENT_CHARS = 500


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
    # Kèm phần đầu tệp đính kèm (vd. mô tả ảnh) để brief kiểu "viết về sản phẩm trong ảnh" vẫn tra được tài liệu
    parts = [state["campaign_topic"], *(a[:RAG_QUERY_ATTACHMENT_CHARS] for a in state.get("attachment_context", []))]
    if feedback := state.get("outline_feedback"):
        parts.append(feedback)
    query = "\n".join(parts)
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
