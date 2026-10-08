import json

from app.agent.nodes.analyze_brief import MAX_NEEDS, parse_plan


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
