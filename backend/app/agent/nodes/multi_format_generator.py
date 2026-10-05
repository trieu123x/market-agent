import asyncio
import logging

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage

from app.agent import llm_factory
from app.agent.prompts import external_context, load_prompt
from app.agent.state import PLATFORMS, AgentState
from app.guardrails.output_scanner import redact_secrets

logger = logging.getLogger(__name__)

PLATFORM_RULES = {
    "linkedin": "Kênh: LinkedIn. 120–250 từ, giọng chuyên nghiệp. Câu đầu là hook nêu insight hoặc vấn đề; "
    "đoạn ngắn, xuống dòng nhiều; kết bằng call-to-action; tối đa 3 hashtag ở cuối.",
    "twitter": "Kênh: X (Twitter). Một thread 3–5 tweet, mỗi tweet tối đa 280 ký tự, đánh số 1/, 2/, ...; "
    "tweet đầu là hook; tối đa 2 hashtag cho cả thread.",
    "facebook": "Kênh: Facebook. 80–180 từ, giọng gần gũi, đoạn ngắn, có thể dùng 1–3 emoji; "
    "kết bằng call-to-action rõ ràng.",
}


def source_block(state: AgentState) -> str:
    """NGUỒN dùng chung cho generator / fact-checker / refine: tài liệu RAG (cách ly), brief, dàn ý đã duyệt."""
    return "\n\n".join(
        [
            external_context(state.get("retrieved_rag_context", [])),
            f"Brief chiến dịch:\n{state['campaign_topic']}",
            f"Dàn ý đã duyệt:\n{state.get('outline') or ''}",
        ]
    )


async def write_post(llm: BaseChatModel, system_prompt: str, user_prompt: str, platform: str) -> str:
    """Gọi LLM cho một kênh (metadata `platform` đi theo event token SSE) rồi che secret lọt ra."""
    response = await llm.with_config(metadata={"platform": platform}).ainvoke(
        [SystemMessage(system_prompt), HumanMessage(user_prompt)]
    )
    text, secrets = redact_secrets(llm_factory.message_text(response).strip())
    if secrets:
        logger.warning("redacted %s from %s draft", secrets, platform)
    return text


async def multi_format_generator(state: AgentState) -> dict:
    """Viết song song 3 bản thảo LinkedIn / X / Facebook từ dàn ý đã duyệt."""
    llm = llm_factory.get_chat_model(state["selected_model"])
    system_prompt, sources = load_prompt("generator"), source_block(state)
    posts = await asyncio.gather(
        *(write_post(llm, system_prompt, f"{sources}\n\n{PLATFORM_RULES[p]}", p) for p in PLATFORMS)
    )
    return {"drafts": dict(zip(PLATFORMS, posts)), "retry_count": 0, "fact_check_report": None}
