from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from app.agent import llm_factory
from app.agent.prompts import load_prompt, reference_context
from app.agent.state import AgentState

KIND_LABELS = {"skill": "Kỹ năng", "knowledge": "Kiến thức"}


def knowledge_plan_block(state: AgentState) -> str | None:
    """Kỹ năng & kiến thức analyze_brief đã xác định, kèm số [i] của tài liệu truy xuất được cho từng cái."""
    plan = state.get("knowledge_plan") or []
    if not plan:
        return None
    sources = state.get("retrieved_sources", [])
    lines = []
    for need in plan:
        refs = ", ".join(f"[{s['ref']}]" for s in sources if need["name"] in s.get("needs", []))
        found = f"tài liệu {refs}" if refs else "không tìm thấy tài liệu"
        lines.append(f"- [{KIND_LABELS[need['kind']]}] {need['name']}: {need['why']} → {found}")
    return "<knowledge_plan>\n" + "\n".join(lines) + "\n</knowledge_plan>"


def _user_prompt(state: AgentState) -> str:
    parts = [reference_context(state), f"Brief chiến dịch:\n{state['campaign_topic']}"]
    if plan := knowledge_plan_block(state):
        parts.insert(1, plan)
    if feedback := state.get("outline_feedback"):
        parts.append(f"Dàn ý trước đã bị từ chối:\n{state.get('outline') or ''}")
        parts.append(f"Phản hồi của người dùng (ưu tiên làm theo):\n{feedback}")
    return "\n\n".join(parts)


async def generate_outline(state: AgentState) -> dict:
    llm = llm_factory.get_chat_model(state["selected_model"])
    response = await llm.ainvoke([SystemMessage(load_prompt("outline")), HumanMessage(_user_prompt(state))])
    outline = llm_factory.message_text(response).strip()
    return {"outline": outline, "outline_status": None, "messages": [AIMessage(outline)]}
