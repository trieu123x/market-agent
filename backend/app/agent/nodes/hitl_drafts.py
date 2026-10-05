from typing import Any

from langgraph.types import interrupt

from app.agent.state import PLATFORMS, AgentState

STAGE = "DRAFTS_APPROVAL"


def hitl_drafts(state: AgentState) -> dict:
    """Điểm ngắt số 2: dừng chờ người dùng approve / edit bộ bản thảo đã qua fact-check."""
    decision: dict[str, Any] = interrupt(
        {
            "stage": STAGE,
            "message": "Bản thảo đã qua bước Fact-checking. Bạn có muốn duyệt hoặc tinh chỉnh?",
            "drafts": state["drafts"],
            "fact_check_report": state.get("fact_check_report"),
        }
    )
    if str(decision.get("action", "approve")).lower() == "edit":
        edited = {p: v for p, v in (decision.get("updated_drafts") or {}).items() if p in PLATFORMS}
        return {"drafts": {**state["drafts"], **edited}, "drafts_status": "edited"}
    return {"drafts_status": "approved"}
