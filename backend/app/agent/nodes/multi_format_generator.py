import asyncio
import logging

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage

from app.agent import llm_factory
from app.agent.prompts import load_prompt, reference_context
from app.agent.state import PLATFORMS, AgentState
from app.guardrails.output_scanner import redact_secrets

logger = logging.getLogger(__name__)

PLATFORM_RULES = {
    "facebook": "Kênh: Facebook. 80–180 từ, giọng gần gũi, đoạn ngắn, có thể dùng 1–3 emoji; "
    "kết bằng call-to-action rõ ràng.",
    "instagram": "Kênh: Instagram. Caption 60–150 từ, giọng trẻ trung, giàu hình ảnh. Dòng đầu (dưới 125 ký tự) "
    "là hook vì bị cắt sau \"... xem thêm\"; đoạn ngắn, 2–4 emoji; kết bằng call-to-action (vd. link ở bio, "
    "lưu bài, nhắn tin); 5–10 hashtag ở cuối, trộn hashtag tiếng Việt và ngách. Mở đầu bằng một dòng "
    "[Gợi ý hình ảnh: ...] mô tả ảnh/carousel đi kèm.",
    "threads": "Kênh: Threads. Một chuỗi 3–5 bài, mỗi bài tối đa 500 ký tự, đánh số 1/, 2/, ..., các bài cách nhau "
    "một dòng trống; giọng trò chuyện, thẳng thắn như đang tán gẫu; bài đầu là hook gây tò mò hoặc nêu "
    "quan điểm; bài cuối mời bình luận hoặc call-to-action; tối đa 1 hashtag (topic tag) cho cả chuỗi.",
}


def source_block(state: AgentState) -> str:
    """NGUỒN dùng chung cho generator / fact-checker / refine: tệp đính kèm + tài liệu RAG (cách ly), brief, dàn ý đã duyệt."""
    return "\n\n".join(
        [
            reference_context(state),
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
    """Viết song song 3 bản thảo Facebook / Instagram / Threads từ dàn ý đã duyệt."""
    llm = llm_factory.get_chat_model(state["selected_model"])
    system_prompt, sources = load_prompt("generator"), source_block(state)
    posts = await asyncio.gather(
        *(write_post(llm, system_prompt, f"{sources}\n\n{PLATFORM_RULES[p]}", p) for p in PLATFORMS)
    )
    return {"drafts": dict(zip(PLATFORMS, posts)), "retry_count": 0, "fact_check_report": None}
