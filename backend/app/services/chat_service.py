import json
import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import ChatThread, ThreadMessage
from app.db.session import SessionLocal


class ThreadNotFound(Exception):
    """Thread không tồn tại hoặc thuộc user khác."""


async def get_owned_thread(session: AsyncSession, user_id: uuid.UUID, thread_id: str) -> ChatThread | None:
    thread = await session.get(ChatThread, thread_id)
    return thread if thread is not None and thread.user_id == user_id else None


async def get_or_create_thread(session: AsyncSession, user_id: uuid.UUID, thread_id: str, title: str) -> ChatThread:
    thread = await session.get(ChatThread, thread_id)
    if thread is None:
        thread = ChatThread(id=thread_id, user_id=user_id, title=title[:255])
        session.add(thread)
        await session.flush()
    elif thread.user_id != user_id:
        raise ThreadNotFound(thread_id)
    return thread


async def list_threads(session: AsyncSession, user_id: uuid.UUID) -> list[ChatThread]:
    stmt = select(ChatThread).where(ChatThread.user_id == user_id).order_by(ChatThread.updated_at.desc())
    return list(await session.scalars(stmt))


async def delete_thread(session: AsyncSession, thread: ChatThread) -> None:
    """Xóa thread: thread_messages theo ON DELETE CASCADE, llm_cost_logs giữ lại (thread_id → NULL) cho audit."""
    await session.delete(thread)
    await session.commit()


async def list_messages(session: AsyncSession, thread_id: str) -> list[ThreadMessage]:
    stmt = select(ThreadMessage).where(ThreadMessage.thread_id == thread_id).order_by(ThreadMessage.created_at)
    return list(await session.scalars(stmt))


def add_message(
    session: AsyncSession,
    thread_id: str,
    sender_role: str,
    content: str,
    content_type: str = "TEXT",
    metadata: dict[str, Any] | None = None,
) -> ThreadMessage:
    msg = ThreadMessage(
        thread_id=thread_id,
        sender_role=sender_role,
        content=content,
        content_type=content_type,
        metadata_=metadata or {},
    )
    session.add(msg)
    return msg


async def record_final_event(thread_id: str, event: str, data: dict[str, Any]) -> None:
    """Lưu kết quả cuối của một lượt stream vào thread_messages (session riêng vì chạy trong StreamingResponse)."""
    async with SessionLocal() as session:
        if event == "hitl_interrupt" and data["stage"] == "OUTLINE_APPROVAL":
            meta = {"stage": data["stage"], "sources": data["data"].get("sources", [])}
            add_message(session, thread_id, "ASSISTANT", data["data"]["outline"], "OUTLINE_CARD", meta)
        elif event == "hitl_interrupt" and data["stage"] == "DRAFTS_APPROVAL":
            meta = {"stage": data["stage"]}
            drafts, report = data["data"]["drafts"], data["data"].get("fact_check_report")
            add_message(session, thread_id, "ASSISTANT", json.dumps(drafts, ensure_ascii=False), "DRAFTS_CARD", meta)
            if report:
                add_message(
                    session, thread_id, "ASSISTANT", json.dumps(report, ensure_ascii=False), "FACT_CHECK_REPORT", meta
                )
        elif event == "error":
            add_message(session, thread_id, "SYSTEM", data["message"], metadata={"code": data["code"]})
        else:
            return
        await session.commit()
