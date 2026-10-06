"""Chuyển `astream_events` của LangGraph thành các event SSE:
status, token, cost_update, hitl_interrupt, error, complete."""
import json
import logging
import uuid
from collections.abc import AsyncIterator
from typing import Any

from langgraph.graph.state import CompiledStateGraph

from app.agent.graph import pending_interrupt, thread_config
from app.agent.llm_factory import LLMConfigError, message_text
from app.services import cost_service

logger = logging.getLogger(__name__)

NODE_STATUS = {
    "input_guardrail": ("INPUT_GUARDRAIL", "Đang kiểm tra an toàn nội dung..."),
    "intent_rag": ("RAG_RETRIEVAL", "Đang phân tích brief và truy xuất tài liệu..."),
    "generate_outline": ("GENERATING_OUTLINE", "Đang soạn dàn ý chiến dịch..."),
    "multi_format_generator": ("GENERATING_DRAFTS", "Đang viết bản thảo Facebook, Instagram, Threads..."),
    "fact_checker": ("FACT_CHECKING", "Đang đối soát số liệu..."),
    "refine_generator": ("REFINING_DRAFTS", "Đang sửa bản thảo theo kết quả fact-check..."),
    "finalize_log": ("FINALIZING", "Đang lưu bản thảo cuối..."),
}
# Chỉ stream token của các node sinh nội dung cho người đọc (fact-checker trả JSON nội bộ)
TOKEN_NODES = {"generate_outline", "multi_format_generator", "refine_generator"}

Event = tuple[str, dict[str, Any]]


def format_sse(event: str, data: dict[str, Any]) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False, default=str)}\n\n"


def _map_event(ev: dict) -> Event | None:
    kind, metadata = ev["event"], ev.get("metadata", {})
    node = metadata.get("langgraph_node")
    if kind == "on_chain_start" and ev["name"] == node and node in NODE_STATUS:
        step, message = NODE_STATUS[node]
        return "status", {"step": step, "message": message}
    if kind == "on_chat_model_stream" and node in TOKEN_NODES:
        if token := message_text(ev["data"]["chunk"]):
            data = {"node": node, "token": token}
            if platform := metadata.get("platform"):
                data["platform"] = platform
            return "token", data
    return None


async def _record_cost(ev: dict, user_id: uuid.UUID, thread_id: str, model_id: str) -> Event | None:
    """Cost auditor: mỗi lần gọi LLM xong → 1 dòng llm_cost_logs + event cost_update."""
    usage = getattr(ev["data"].get("output"), "usage_metadata", None)
    node = ev.get("metadata", {}).get("langgraph_node", "unknown")
    if not usage:
        logger.warning("LLM call in node=%s returned no usage_metadata – not logged", node)
        return None
    try:
        rec = await cost_service.record_usage(
            user_id, thread_id, node, model_id, usage.get("input_tokens", 0), usage.get("output_tokens", 0)
        )
    except Exception:
        logger.exception("failed to record LLM cost thread=%s node=%s", thread_id, node)
        return None
    return "cost_update", {
        "node": rec.node,
        "model_id": rec.model_id,
        "prompt_tokens": rec.prompt_tokens,
        "completion_tokens": rec.completion_tokens,
        "tokens": rec.total_tokens,
        "cost_usd": float(rec.cost_usd),
        "pricing_missing": rec.pricing_missing,
    }


def interrupt_event(payload: dict[str, Any]) -> dict[str, Any]:
    """Payload của interrupt() → dữ liệu event hitl_interrupt: {stage, message, data}."""
    data = {k: v for k, v in payload.items() if k not in ("stage", "message")}
    return {"stage": payload["stage"], "message": payload.get("message"), "data": data}


async def _final_event(graph: CompiledStateGraph, thread_id: str) -> Event:
    if (payload := await pending_interrupt(graph, thread_id)) is not None:
        return "hitl_interrupt", interrupt_event(payload)
    values = (await graph.aget_state(thread_config(thread_id))).values
    if violation := values.get("guardrail_violation"):
        return "error", dict(violation)
    tokens, cost = await cost_service.thread_totals(thread_id)
    return "complete", {"thread_id": thread_id, "status": "FINISHED", "total_tokens": tokens, "total_cost_usd": float(cost)}


async def stream_graph(
    graph: CompiledStateGraph, graph_input: Any, thread_id: str, user_id: uuid.UUID, model_id: str
) -> AsyncIterator[Event]:
    """Chạy graph (input mới hoặc Command(resume=...)) và phát event; luôn kết thúc bằng
    đúng một event hitl_interrupt / error / complete."""
    try:
        async for ev in graph.astream_events(graph_input, thread_config(thread_id), version="v2"):
            if ev["event"] == "on_chat_model_end":
                mapped = await _record_cost(ev, user_id, thread_id, model_id)
            else:
                mapped = _map_event(ev)
            if mapped:
                yield mapped
        yield await _final_event(graph, thread_id)
    except LLMConfigError as e:
        yield "error", {"code": "LLM_CONFIG_ERROR", "message": str(e)}
    except Exception:
        logger.exception("agent run failed thread=%s", thread_id)
        yield "error", {"code": "INTERNAL_ERROR", "message": "Đã xảy ra lỗi hệ thống, vui lòng thử lại."}
