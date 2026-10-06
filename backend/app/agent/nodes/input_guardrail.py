import logging

from langchain_core.messages import HumanMessage

from app.agent.state import AgentState
from app.guardrails.injection_classifier import is_prompt_injection
from app.guardrails.input_filter import detect_jailbreak
from app.guardrails.pii import mask_pii

logger = logging.getLogger(__name__)


def _last_user_text(state: AgentState) -> str:
    for msg in reversed(state.get("messages", [])):
        if isinstance(msg, HumanMessage):
            return msg.content if isinstance(msg.content, str) else str(msg.content)
    return state.get("campaign_topic", "")


async def input_guardrail(state: AgentState) -> dict:
    """Vòng 1: regex jailbreak + semantic classifier (stub) + che PII. Rate limit nằm ở API."""
    text = _last_user_text(state)
    attachments = state.get("attachment_context", [])
    # Tệp đính kèm là nội dung người dùng đưa vào: chặn jailbreak như brief (regex, không gọi classifier)
    rule = detect_jailbreak(text) or next(filter(None, map(detect_jailbreak, attachments)), None)
    if rule or await is_prompt_injection(text):
        logger.warning("guardrail blocked thread=%s rule=%s", state.get("thread_id"), rule or "classifier")
        return {"guardrail_violation": {"code": "GUARDRAIL_VIOLATION", "message": "Nội dung vi phạm chính sách."}}

    masked, pii_types = mask_pii(text)
    masked_attachments = []
    for item in attachments:
        item, found = mask_pii(item)
        masked_attachments.append(item)
        pii_types = [*pii_types, *found]
    if pii_types:
        logger.info("masked PII %s in thread=%s", sorted(set(pii_types)), state.get("thread_id"))
    return {"guardrail_violation": None, "campaign_topic": masked, "attachment_context": masked_attachments}
