import logging
import uuid

from app.agent.state import AgentState
from app.db.session import SessionLocal
from app.rag.retriever import RetrievedChunk, retrieve

logger = logging.getLogger(__name__)


def _format_chunk(i: int, chunk: RetrievedChunk) -> str:
    return f"[{i}] {chunk.document_title} (đoạn {chunk.chunk_index})\n{chunk.content}"


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
    return {"retrieved_rag_context": [_format_chunk(i, c) for i, c in enumerate(chunks, start=1)]}
