import logging
import re

from langchain_core.messages import HumanMessage, SystemMessage

from app.agent import llm_factory
from app.agent.prompts import external_context, load_prompt
from app.agent.state import AgentState, KnowledgeNeed

logger = logging.getLogger(__name__)

MAX_NEEDS = 6
ATTACHMENT_CHARS = 1500
KINDS = ("skill", "knowledge")
# Cắt ngắn field do LLM sinh: chúng được đưa lại vào prompt dàn ý nên không để tệp đính kèm "mượn" chỗ này
_LIMITS = {"name": 80, "why": 240, "query": 240}
_ANGLE_RE = re.compile(r"[<>]")  # không để field giả thẻ <knowledge_plan> / <external_context>


def _clean(value: object, limit: int) -> str:
    return " ".join(_ANGLE_RE.sub("", str(value or "")).split())[:limit]


def parse_plan(text: str) -> list[KnowledgeNeed] | None:
    """Đọc JSON kế hoạch truy xuất; bỏ mục thiếu field/sai kind. None nếu không đọc được."""
    data = llm_factory.json_object(text)
    if data is None or not isinstance(data.get("needs"), list):
        return None
    needs: list[KnowledgeNeed] = []
    for item in data["needs"]:
        if not isinstance(item, dict) or str(item.get("kind", "")).lower() not in KINDS:
            continue
        fields = {k: _clean(item.get(k), limit) for k, limit in _LIMITS.items()}
        if fields["name"] and fields["query"]:
            needs.append(KnowledgeNeed(kind=str(item["kind"]).lower(), **fields))
    return needs[:MAX_NEEDS]


def _user_prompt(state: AgentState) -> str:
    parts = [f"Brief chiến dịch:\n{state['campaign_topic']}"]
    if attachments := state.get("attachment_context"):
        parts.insert(0, external_context([a[:ATTACHMENT_CHARS] for a in attachments]))
    if feedback := state.get("outline_feedback"):
        parts.append(f"Phản hồi từ chối dàn ý trước:\n{feedback}")
    return "\n\n".join(parts)


async def analyze_brief(state: AgentState) -> dict:
    """Viết lại brief thành các kỹ năng & kiến thức cần để lên ý tưởng, mỗi cái một truy vấn RAG.
    Không đọc được output → kế hoạch rỗng, intent_rag chỉ tra theo brief như cũ."""
    llm = llm_factory.get_chat_model(state["selected_model"])
    response = await llm.ainvoke([SystemMessage(load_prompt("query_planner")), HumanMessage(_user_prompt(state))])
    plan = parse_plan(llm_factory.message_text(response))
    if plan is None:
        logger.warning("query planner output unparsable for thread=%s", state.get("thread_id"))
        plan = []
    return {"knowledge_plan": plan}
