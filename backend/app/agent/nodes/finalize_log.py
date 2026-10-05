import json

from langchain_core.messages import AIMessage

from app.agent.state import AgentState
from app.db.session import SessionLocal
from app.services import chat_service


async def finalize_log(state: AgentState) -> dict:
    """Lưu bộ bản thảo cuối vào thread_messages. Chi phí từng lần gọi LLM đã được ghi khi stream (cost auditor)."""
    report = state.get("fact_check_report") or {}
    async with SessionLocal() as session:
        chat_service.add_message(
            session,
            state["thread_id"],
            "ASSISTANT",
            json.dumps(state["drafts"], ensure_ascii=False),
            "DRAFTS_CARD",
            {"final": True, "status": state.get("drafts_status"), "fact_check_passed": report.get("passed")},
        )
        await session.commit()
    return {"messages": [AIMessage("Bản thảo cuối đã được duyệt.")]}
