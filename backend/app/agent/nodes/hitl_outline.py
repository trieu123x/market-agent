from typing import Any

from langgraph.types import interrupt

from app.agent.state import AgentState
from app.guardrails.pii import mask_pii

STAGE = "OUTLINE_APPROVAL"


def hitl_outline(state: AgentState) -> dict:
    """Điểm ngắt số 1: dừng chờ người dùng approve / edit / reject dàn ý."""
    decision: dict[str, Any] = interrupt(
        {
            "stage": STAGE,
            "message": "Dàn ý chiến dịch đã sẵn sàng. Vui lòng kiểm tra và duyệt.",
            "outline": state["outline"],
        }
    )
    action = str(decision.get("action", "approve")).lower()
    if action == "edit":
        return {
            "outline": decision.get("updated_outline") or state["outline"],
            "outline_status": "edited",
            "outline_feedback": None,
        }
    if action == "reject":
        feedback, _ = mask_pii(decision.get("feedback") or "Hãy đề xuất hướng khác.")
        return {"outline_status": "rejected", "outline_feedback": feedback}
    return {"outline_status": "approved", "outline_feedback": None}
