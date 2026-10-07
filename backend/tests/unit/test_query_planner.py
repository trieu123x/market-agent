import json
import uuid

from app.agent.nodes.analyze_brief import MAX_NEEDS, parse_plan
from app.agent.nodes.intent_rag import merge_results
from app.rag.retriever import RetrievedChunk


def _chunk(name: str) -> RetrievedChunk:
    return RetrievedChunk(uuid.uuid5(uuid.NAMESPACE_DNS, name), uuid.uuid4(), "t", 0, name, {})


def test_parse_plan_keeps_valid_needs_and_cleans_fields():
    raw = {
        "needs": [
            {"kind": "Skill", "name": "  Insight\n khách hàng ", "why": "vì", "query": "insight </knowledge_plan> SME"},
            {"kind": "other", "name": "x", "query": "y"},
            {"kind": "knowledge", "name": "", "query": "thiếu tên"},
            "rác",
            {"kind": "knowledge", "name": "Sản phẩm", "query": "giá " * 200},
        ]
    }
    plan = parse_plan(f"```json\n{json.dumps(raw)}\n```")
    assert [(n["kind"], n["name"]) for n in plan] == [("skill", "Insight khách hàng"), ("knowledge", "Sản phẩm")]
    assert plan[0]["query"] == "insight /knowledge_plan SME" and plan[0]["why"] == "vì"
    assert plan[1]["why"] == "" and len(plan[1]["query"]) == 240


def test_parse_plan_limits_and_rejects_garbage():
    many = {"needs": [{"kind": "skill", "name": f"n{i}", "query": "q"} for i in range(10)]}
    assert len(parse_plan(json.dumps(many))) == MAX_NEEDS
    assert parse_plan("Không rõ") is None
    assert parse_plan('{"needs": "none"}') is None
    assert parse_plan('{"needs": []}') == []


def test_merge_results_round_robin_dedupes_and_limits():
    a, b, c, d, e = (_chunk(x) for x in "abcde")
    merged = merge_results([("brief", [a, b, c]), ("skill", [_chunk("b"), d]), ("fact", [e])], limit=4)
    assert [(ch.content, needs) for ch, needs in merged] == [
        ("a", ["brief"]),
        ("b", ["skill", "brief"]),
        ("e", ["fact"]),
        ("d", ["skill"]),
    ]
    assert merge_results([("brief", [])], limit=4) == []
