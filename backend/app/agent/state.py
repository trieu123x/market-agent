from typing import Annotated, Optional

from langgraph.graph.message import add_messages
from typing_extensions import TypedDict


PLATFORMS = ("linkedin", "twitter", "facebook")
MAX_REFINES = 2  # spec: refine khi còn lỗi và retry < 2


class GuardrailViolation(TypedDict):
    code: str
    message: str


class FactCheckIssue(TypedDict):
    platform: str
    kind: str  # "fact" (fact-checker LLM) | "cliche" (output guardrail)
    claim: str
    problem: str
    suggestion: str


class FactCheckReport(TypedDict):
    passed: bool
    summary: str
    issues: list[FactCheckIssue]
    round: int  # số lần đã refine trước lượt kiểm tra này


class AgentState(TypedDict, total=False):
    thread_id: str
    user_id: str
    selected_model: str
    messages: Annotated[list, add_messages]

    # Brief & RAG context (campaign_topic đã che PII)
    campaign_topic: str
    retrieved_rag_context: list[str]
    web_search_context: list[str]
    guardrail_violation: Optional[GuardrailViolation]

    # HITL 1: dàn ý
    outline: Optional[str]
    outline_status: Optional[str]  # "approved" | "edited" | "rejected"
    outline_feedback: Optional[str]  # lý do reject, dùng cho lượt sinh dàn ý kế tiếp

    # Bản thảo đa kênh: {"linkedin": "...", "twitter": "...", "facebook": "..."}
    drafts: dict[str, str]

    # Fact-checking & self-correction
    fact_check_passed: bool
    fact_check_report: Optional[FactCheckReport]
    retry_count: int

    # HITL 2: bản thảo cuối
    drafts_status: Optional[str]
