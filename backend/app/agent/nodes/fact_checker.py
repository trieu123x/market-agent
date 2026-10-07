import logging

from langchain_core.messages import HumanMessage, SystemMessage

from app.agent import llm_factory
from app.agent.nodes.multi_format_generator import source_block
from app.agent.prompts import load_prompt
from app.agent.state import PLATFORMS, AgentState, FactCheckIssue
from app.guardrails.output_scanner import find_cliches

logger = logging.getLogger(__name__)


def parse_checker_output(text: str) -> tuple[bool, str, list[FactCheckIssue]] | None:
    """Đọc JSON của fact-checker (chịu được code fence / lời dẫn quanh JSON). None nếu không đọc được."""
    data = llm_factory.json_object(text)
    if data is None or not isinstance(data.get("issues", []), list):
        return None
    issues: list[FactCheckIssue] = [
        {
            "platform": str(i.get("platform", "")).lower(),
            "kind": "fact",
            "claim": str(i.get("claim", "")),
            "problem": str(i.get("problem", "")),
            "suggestion": str(i.get("suggestion", "")),
        }
        for i in data.get("issues", [])
        if isinstance(i, dict)
    ]
    passed = bool(data.get("passed", not issues)) and not issues
    return passed, str(data.get("summary", "")), issues


def _cliche_issues(drafts: dict[str, str]) -> list[FactCheckIssue]:
    return [
        {
            "platform": platform,
            "kind": "cliche",
            "claim": phrase,
            "problem": "Cụm từ sáo rỗng kiểu AI",
            "suggestion": "Thay bằng chi tiết cụ thể về sản phẩm hoặc khách hàng",
        }
        for platform in PLATFORMS
        for phrase in find_cliches(drafts.get(platform, ""))
    ]


async def fact_checker(state: AgentState) -> dict:
    """Đối soát bản thảo với NGUỒN (LLM) + lọc sáo rỗng (regex). passed = không còn issue nào."""
    drafts = state["drafts"]
    drafts_xml = "\n\n".join(f'<draft platform="{p}">\n{drafts.get(p, "")}\n</draft>' for p in PLATFORMS)
    llm = llm_factory.get_chat_model(state["selected_model"])
    response = await llm.ainvoke(
        [
            SystemMessage(load_prompt("fact_checker")),
            HumanMessage(f"NGUỒN:\n{source_block(state)}\n\nBẢN THẢO CẦN KIỂM TRA:\n{drafts_xml}"),
        ]
    )
    parsed = parse_checker_output(llm_factory.message_text(response))
    if parsed is None:
        logger.warning("fact-checker output unparsable for thread=%s", state.get("thread_id"))
        summary, issues = "Không đọc được kết quả fact-check, cần kiểm tra thủ công.", []
    else:
        _, summary, issues = parsed

    issues = issues + _cliche_issues(drafts)
    passed = not issues
    report = {"passed": passed, "summary": summary, "issues": issues, "round": state.get("retry_count", 0)}
    return {"fact_check_passed": passed, "fact_check_report": report}
