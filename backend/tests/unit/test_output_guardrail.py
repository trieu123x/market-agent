from decimal import Decimal

from app.agent.nodes.fact_checker import parse_checker_output
from app.db.models import ModelPricing
from app.guardrails.output_scanner import find_cliches, redact_secrets
from app.services.cost_service import compute_cost


def test_redact_secrets():
    text = (
        "Key sk-ant-api03-" + "x" * 30 + " và AIza" + "B" * 35 + " và AKIAABCDEFGHIJKLMNOP, "
        "token ghp_" + "a" * 36 + ", password: hunter2hunter2"
    )
    redacted, found = redact_secrets(text)
    assert "sk-ant" not in redacted and "AIza" not in redacted and "AKIA" not in redacted and "ghp_" not in redacted
    assert "hunter2" not in redacted and redacted.count("[REDACTED]") == 5
    assert set(found) == {"anthropic_key", "google_key", "aws_access_key", "github_token", "credential_assignment"}


def test_redact_keeps_normal_marketing_text():
    text = "Ưu đãi 20% cho 1000 doanh nghiệp, mã SKU-2026, liên hệ hotline 1900 1234."
    assert redact_secrets(text) == (text, [])


def test_find_cliches():
    text = "Trong thời đại số, PayNow sẽ NÂNG TẦM doanh nghiệp. Nâng tầm hơn nữa! A game-changer."
    assert find_cliches(text) == ["trong thời đại số", "nâng tầm", "game-changer"]
    assert find_cliches("CFO tiết kiệm 3 ngày đối soát mỗi tháng.") == []


def test_parse_checker_output_variants():
    ok = '{"passed": true, "summary": "Ổn", "issues": []}'
    assert parse_checker_output(ok) == (True, "Ổn", [])
    fenced = '```json\n{"passed": false, "summary": "Sai", "issues": [{"platform": "Instagram", "claim": "50%",' \
        ' "problem": "không có nguồn", "suggestion": "bỏ"}]}\n```'
    passed, summary, issues = parse_checker_output(fenced)
    assert passed is False and summary == "Sai"
    assert issues == [{"platform": "instagram", "kind": "fact", "claim": "50%", "problem": "không có nguồn", "suggestion": "bỏ"}]
    # passed=true nhưng vẫn có issue → coi là fail
    contradictory = '{"passed": true, "issues": [{"platform": "threads", "claim": "x"}]}'
    assert parse_checker_output(contradictory)[0] is False
    assert parse_checker_output("Tôi không chắc.") is None
    assert parse_checker_output('{"passed": true, "issues": "none"}') is None


def test_compute_cost_rounds_to_micro_usd():
    pricing = ModelPricing(input_price_per_1k=Decimal("0.000300"), output_price_per_1k=Decimal("0.002500"))
    assert compute_cost(pricing, 505, 952) == Decimal("0.002532")
    assert compute_cost(pricing, 0, 0) == Decimal("0.000000")
