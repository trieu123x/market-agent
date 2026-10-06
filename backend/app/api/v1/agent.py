import uuid
from collections.abc import AsyncIterator
from typing import Any

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.responses import StreamingResponse
from langchain_core.messages import HumanMessage
from langgraph.types import Command
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent import llm_factory
from app.agent.graph import get_graph, pending_interrupt, thread_config
from app.agent.streaming import format_sse, interrupt_event, stream_graph
from app.api.deps import get_current_user, read_upload
from app.core.config import get_settings
from app.db.models import User
from app.db.session import get_session
from app.guardrails.input_filter import detect_jailbreak
from app.guardrails.rate_limiter import get_rate_limiter
from app.schemas.agent import (
    AttachmentOut,
    ChatResumeRequest,
    ChatStreamRequest,
    ModelOption,
    PendingInterrupt,
    ThreadMessageOut,
    ThreadOut,
    ThreadStateOut,
)
from app.services import attachment_service, chat_service, cost_service, pricing_service

router = APIRouter(prefix="/agent", tags=["agent"])

# Tắt buffer của proxy (nginx) để token tới client ngay
SSE_HEADERS = {"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}


async def rate_limit(user: User = Depends(get_current_user)) -> User:
    if not await get_rate_limiter().hit(f"agent:{user.id}"):
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "Quá nhiều yêu cầu, vui lòng thử lại sau ít phút")
    return user


def _sse_response(graph_input: Any, thread_id: str, user_id: uuid.UUID, model_id: str) -> StreamingResponse:
    async def body() -> AsyncIterator[str]:
        yield format_sse("status", {"step": "STARTED", "message": "Bắt đầu xử lý...", "thread_id": thread_id})
        graph = await get_graph()
        async for event, data in stream_graph(graph, graph_input, thread_id, user_id, model_id):
            if event in ("hitl_interrupt", "error"):
                await chat_service.record_final_event(thread_id, event, data)
            yield format_sse(event, data)

    return StreamingResponse(
        body(), media_type="text/event-stream", headers={**SSE_HEADERS, "X-Thread-Id": thread_id}
    )


@router.post("/chat/stream")
async def chat_stream(
    body: ChatStreamRequest, user: User = Depends(rate_limit), session: AsyncSession = Depends(get_session)
):
    """Bắt đầu một lượt chat mới trên thread (tạo thread nếu chưa có) và stream kết quả qua SSE."""
    pricing = await pricing_service.resolve_active_model(session, body.model_id)
    if pricing is None:
        detail = f"Model '{body.model_id}' không tồn tại hoặc đã bị tắt" if body.model_id else "Chưa cấu hình model mặc định"
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail)
    try:
        llm_factory.get_chat_model(pricing.model_id)
    except llm_factory.LLMConfigError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e))

    thread_id = body.thread_id or f"thread_{uuid.uuid4().hex}"
    try:
        await chat_service.get_or_create_thread(session, user.id, thread_id, body.message[:80])
    except chat_service.ThreadNotFound:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Thread not found")
    if await pending_interrupt(await get_graph(), thread_id) is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Thread đang chờ duyệt, dùng /agent/chat/resume")

    attachments = [a.model_dump() for a in body.attachments]
    metadata = {"attachments": attachments} if attachments else None
    chat_service.add_message(session, thread_id, "USER", body.message, metadata=metadata)
    await session.commit()

    # Reset các field của lượt trước: thread đã xong có thể bắt đầu brief mới
    graph_input = {
        "thread_id": thread_id,
        "user_id": str(user.id),
        "selected_model": pricing.model_id,
        "messages": [HumanMessage(body.message)],
        "campaign_topic": body.message,
        "attachment_context": [attachment_service.format_for_context(**a) for a in attachments],
        "retrieved_rag_context": [],
        "retrieved_sources": [],
        "web_search_context": [],
        "guardrail_violation": None,
        "outline": None,
        "outline_status": None,
        "outline_feedback": None,
        "drafts": {},
        "fact_check_passed": False,
        "fact_check_report": None,
        "retry_count": 0,
        "drafts_status": None,
    }
    return _sse_response(graph_input, thread_id, user.id, pricing.model_id)


@router.post("/attachments", response_model=AttachmentOut)
async def upload_attachment(
    file: UploadFile = File(...),
    thread_id: str | None = Form(default=None),
    user: User = Depends(rate_limit),
    session: AsyncSession = Depends(get_session),
):
    """Trích nội dung tệp đính kèm cho lượt chat: tài liệu qua parser RAG, ảnh qua Gemini.
    Không lưu file; client gửi lại kết quả trong `attachments` của /chat/stream."""
    data = await read_upload(file, get_settings().max_upload_bytes)
    # Chỉ gắn chi phí phân tích ảnh vào thread của chính user; thread mới (chưa tạo) → NULL
    if thread_id and await chat_service.get_owned_thread(session, user.id, thread_id) is None:
        thread_id = None
    try:
        att = await attachment_service.process(file.filename or "upload", data, user.id, thread_id)
    except attachment_service.AttachmentError as e:
        raise HTTPException(status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, str(e))
    except attachment_service.VisionError as e:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, str(e))
    return AttachmentOut(**vars(att))


@router.post("/chat/resume")
async def chat_resume(
    body: ChatResumeRequest, user: User = Depends(rate_limit), session: AsyncSession = Depends(get_session)
):
    """Gửi quyết định HITL (APPROVE / EDIT / REJECT) và stream phần còn lại của luồng."""
    if await chat_service.get_owned_thread(session, user.id, body.thread_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Thread not found")
    snapshot = await (await get_graph()).aget_state(thread_config(body.thread_id))
    pending = snapshot.interrupts[0].value if snapshot.interrupts else None
    if pending is None or pending.get("stage") != body.stage:
        raise HTTPException(status.HTTP_409_CONFLICT, f"Thread không chờ duyệt ở bước {body.stage}")
    if any(detect_jailbreak(t) for t in (body.feedback, body.updated_outline) if t):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Nội dung vi phạm chính sách.")

    decision = body.model_dump(exclude={"thread_id", "stage"}, exclude_none=True)
    chat_service.add_message(
        session, body.thread_id, "HUMAN_INTERRUPT", body.action, metadata={"stage": body.stage, **decision}
    )
    await session.commit()
    return _sse_response(
        Command(resume={**decision, "action": body.action.lower()}),
        body.thread_id,
        user.id,
        snapshot.values["selected_model"],
    )


@router.get("/models", response_model=list[ModelOption])
async def list_models(_: User = Depends(get_current_user), session: AsyncSession = Depends(get_session)):
    """Model đang active cho người dùng chọn (model mặc định đứng đầu)."""
    return [
        ModelOption(
            model_id=m.model_id,
            provider=m.provider,
            is_default=m.is_default,
            available=llm_factory.provider_configured(m.provider),
        )
        for m in await pricing_service.list_active(session)
    ]


@router.get("/threads", response_model=list[ThreadOut])
async def list_threads(user: User = Depends(get_current_user), session: AsyncSession = Depends(get_session)):
    return await chat_service.list_threads(session, user.id)


@router.get("/threads/{thread_id}/messages", response_model=list[ThreadMessageOut])
async def list_messages(
    thread_id: str, user: User = Depends(get_current_user), session: AsyncSession = Depends(get_session)
):
    if await chat_service.get_owned_thread(session, user.id, thread_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Thread not found")
    return await chat_service.list_messages(session, thread_id)


@router.get("/threads/{thread_id}/state", response_model=ThreadStateOut)
async def thread_state(
    thread_id: str, user: User = Depends(get_current_user), session: AsyncSession = Depends(get_session)
):
    """HITL đang chờ (để mở lại modal duyệt khi load lại thread) + tổng token/chi phí của thread."""
    if await chat_service.get_owned_thread(session, user.id, thread_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Thread not found")
    payload = await pending_interrupt(await get_graph(), thread_id)
    pending = PendingInterrupt(**interrupt_event(payload)) if payload is not None else None
    tokens, cost = await cost_service.thread_totals(thread_id)
    return ThreadStateOut(thread_id=thread_id, pending=pending, total_tokens=tokens, total_cost_usd=float(cost))
