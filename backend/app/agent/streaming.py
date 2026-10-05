"""Chuyển `astream_events` của LangGraph thành các event SSE: status, token, hitl_interrupt, error, complete."""
import json
import logging
from collections.abc import AsyncIterator
from typing import Any

from langgraph.graph.state import CompiledStateGraph

from app.agent.graph import pending_interrupt, thread_config
from app.agent.llm_factory import LLMConfigError, message_text

logger = logging.getLogger(__name__)

NODE_STATUS = {
    "input_guardrail": ("INPUT_GUARDRAIL", "Đang kiểm tra an toàn nội dung..."),
    "intent_rag": ("RAG_RETRIEVAL", "Đang phân tích brief và truy xuất tài liệu..."),
    "generate_outline": ("GENERATING_OUTLINE", "Đang soạn dàn ý chiến dịch..."),
}
# Chỉ stream token của các node sinh nội dung cho người đọc
TOKEN_NODES = {"generate_outline"}

Event = tuple[str, dict[str, Any]]


def format_sse(event: str, data: dict[str, Any]) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False, default=str)}\n\n"


def _map_event(ev: dict) -> Event | None:
    kind, node = ev["event"], ev.get("metadata", {}).get("langgraph_node")
    if kind == "on_chain_start" and ev["name"] == node and node in NODE_STATUS:
        step, message = NODE_STATUS[node]
        return "status", {"step": step, "message": message}
    if kind == "on_chat_model_stream" and node in TOKEN_NODES:
        if token := message_text(ev["data"]["chunk"]):
            return "token", {"node": node, "token": token}
    return None


async def _final_event(graph: CompiledStateGraph, thread_id: str) -> Event:
    if (payload := await pending_interrupt(graph, thread_id)) is not None:
        data = {k: v for k, v in payload.items() if k not in ("stage", "message")}
        return "hitl_interrupt", {"stage": payload["stage"], "message": payload.get("message"), "data": data}
    values = (await graph.aget_state(thread_config(thread_id))).values
    if violation := values.get("guardrail_violation"):
        return "error", dict(violation)
    return "complete", {"thread_id": thread_id, "status": "FINISHED"}


async def stream_graph(graph: CompiledStateGraph, graph_input: Any, thread_id: str) -> AsyncIterator[Event]:
    """Chạy graph (input mới hoặc Command(resume=...)) và phát event; luôn kết thúc bằng
    đúng một event hitl_interrupt / error / complete."""
    try:
        async for ev in graph.astream_events(graph_input, thread_config(thread_id), version="v2"):
            if mapped := _map_event(ev):
                yield mapped
        yield await _final_event(graph, thread_id)
    except LLMConfigError as e:
        yield "error", {"code": "LLM_CONFIG_ERROR", "message": str(e)}
    except Exception:
        logger.exception("agent run failed thread=%s", thread_id)
        yield "error", {"code": "INTERNAL_ERROR", "message": "Đã xảy ra lỗi hệ thống, vui lòng thử lại."}
