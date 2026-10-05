import asyncio

from app.agent import llm_factory
from app.agent.nodes.multi_format_generator import PLATFORM_RULES, source_block, write_post
from app.agent.prompts import load_prompt
from app.agent.state import PLATFORMS, AgentState


def _issue_lines(issues: list[dict]) -> str:
    return "\n".join(f"- \"{i['claim']}\": {i['problem']}. Gợi ý: {i['suggestion']}" for i in issues)


async def refine_generator(state: AgentState) -> dict:
    """Viết lại các bản thảo bị fact-checker nêu lỗi (issue không rõ kênh → sửa cả 3), tăng retry_count."""
    issues = state["fact_check_report"]["issues"]
    by_platform = {p: [i for i in issues if i["platform"] == p or i["platform"] not in PLATFORMS] for p in PLATFORMS}
    targets = [p for p in PLATFORMS if by_platform[p]]

    llm = llm_factory.get_chat_model(state["selected_model"])
    system_prompt, sources, drafts = load_prompt("refine"), source_block(state), state["drafts"]
    rewritten = await asyncio.gather(
        *(
            write_post(
                llm,
                system_prompt,
                f"{sources}\n\n{PLATFORM_RULES[p]}\n\nBài hiện tại:\n{drafts.get(p, '')}\n\n"
                f"Vấn đề cần sửa:\n{_issue_lines(by_platform[p])}",
                p,
            )
            for p in targets
        )
    )
    return {"drafts": {**drafts, **dict(zip(targets, rewritten))}, "retry_count": state.get("retry_count", 0) + 1}
