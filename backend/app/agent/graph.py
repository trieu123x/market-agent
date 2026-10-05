"""StateGraph của agent + graph compile dùng chung (checkpointer Postgres, khởi tạo lười)."""
import asyncio
from typing import Any

from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph
from psycopg_pool import AsyncConnectionPool

from app.agent.checkpointer import open_checkpointer
from app.agent.nodes.generate_outline import generate_outline
from app.agent.nodes.hitl_outline import hitl_outline
from app.agent.nodes.input_guardrail import input_guardrail
from app.agent.nodes.intent_rag import intent_rag
from app.agent.state import AgentState


def _after_guardrail(state: AgentState) -> str:
    return END if state.get("guardrail_violation") else "intent_rag"


def _after_outline_review(state: AgentState) -> str:
    # Ngày 4: approved/edited → multi_format_generator
    return "intent_rag" if state.get("outline_status") == "rejected" else END


def build_graph() -> StateGraph:
    g = StateGraph(AgentState)
    g.add_node("input_guardrail", input_guardrail)
    g.add_node("intent_rag", intent_rag)
    g.add_node("generate_outline", generate_outline)
    g.add_node("hitl_outline", hitl_outline)

    g.add_edge(START, "input_guardrail")
    g.add_conditional_edges("input_guardrail", _after_guardrail, ["intent_rag", END])
    g.add_edge("intent_rag", "generate_outline")
    g.add_edge("generate_outline", "hitl_outline")
    g.add_conditional_edges("hitl_outline", _after_outline_review, ["intent_rag", END])
    return g


_graph: CompiledStateGraph | None = None
_pool: AsyncConnectionPool | None = None
_lock = asyncio.Lock()


async def get_graph() -> CompiledStateGraph:
    global _graph, _pool
    if _graph is None:
        async with _lock:
            if _graph is None:
                saver, _pool = await open_checkpointer()
                _graph = build_graph().compile(checkpointer=saver)
    return _graph


async def close_graph() -> None:
    global _graph, _pool
    if _pool is not None:
        await _pool.close()
    _graph, _pool = None, None


def thread_config(thread_id: str) -> dict:
    return {"configurable": {"thread_id": thread_id}}


async def pending_interrupt(graph: CompiledStateGraph, thread_id: str) -> dict[str, Any] | None:
    """Payload của interrupt đang chờ trên thread (None nếu thread không bị dừng ở HITL)."""
    snapshot = await graph.aget_state(thread_config(thread_id))
    for item in snapshot.interrupts:
        return item.value
    return None
