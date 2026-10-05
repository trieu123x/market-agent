from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from app.agent import llm_factory
from app.agent.prompts import external_context, load_prompt
from app.agent.state import AgentState


def _user_prompt(state: AgentState) -> str:
    parts = [external_context(state.get("retrieved_rag_context", [])), f"Brief chiến dịch:\n{state['campaign_topic']}"]
    if feedback := state.get("outline_feedback"):
        parts.append(f"Dàn ý trước đã bị từ chối:\n{state.get('outline') or ''}")
        parts.append(f"Phản hồi của người dùng (ưu tiên làm theo):\n{feedback}")
    return "\n\n".join(parts)


async def generate_outline(state: AgentState) -> dict:
    llm = llm_factory.get_chat_model(state["selected_model"])
    response = await llm.ainvoke([SystemMessage(load_prompt("outline")), HumanMessage(_user_prompt(state))])
    outline = llm_factory.message_text(response).strip()
    return {"outline": outline, "outline_status": None, "messages": [AIMessage(outline)]}
