"""Vòng 3 – output guardrail: che secret lọt ra bản thảo + phát hiện cụm từ sáo rỗng kiểu AI."""
import re
import unicodedata

_SECRET_PATTERNS = {
    "private_key": r"-----BEGIN [A-Z ]*PRIVATE KEY-----[\s\S]*?-----END [A-Z ]*PRIVATE KEY-----",
    "anthropic_key": r"\bsk-ant-[A-Za-z0-9_-]{20,}",
    "openai_key": r"\bsk-(?:proj-)?[A-Za-z0-9_-]{20,}",
    "google_key": r"\bAIza[0-9A-Za-z_-]{35}\b",
    "aws_access_key": r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b",
    "github_token": r"\bgh[pousr]_[A-Za-z0-9]{36,}\b",
    "slack_token": r"\bxox[abprs]-[A-Za-z0-9-]{10,}",
    "jwt": r"\beyJ[A-Za-z0-9_-]{10,}\.eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}",
    "credential_assignment": r"(?i)\b(?:password|passwd|mật khẩu|api[_ -]?key|secret)\s*[:=]\s*\S{6,}",
}
_SECRET_RES = {name: re.compile(p) for name, p in _SECRET_PATTERNS.items()}

CLICHES = [
    "trong thời đại số",
    "trong thời đại công nghệ",
    "trong bối cảnh hiện nay",
    "hơn bao giờ hết",
    "không thể phủ nhận",
    "nâng tầm",
    "kỷ nguyên mới",
    "cách mạng hóa",
    "khai phá tiềm năng",
    "giải pháp toàn diện",
    "hãy cùng khám phá",
    "đừng bỏ lỡ cơ hội",
    "game-changer",
    "game changer",
    "unlock the power",
    "unleash",
    "in today's fast-paced world",
    "in the ever-evolving",
    "delve into",
    "a testament to",
    "revolutionize",
    "cutting-edge",
    "seamless",
    "elevate your",
]
_CLICHE_RE = re.compile("|".join(re.escape(c) for c in CLICHES), re.IGNORECASE)


def redact_secrets(text: str) -> tuple[str, list[str]]:
    """Thay secret bằng [REDACTED]. Trả (text đã che, các loại secret tìm thấy)."""
    found: list[str] = []
    for name, pattern in _SECRET_RES.items():
        text, n = pattern.subn("[REDACTED]", text)
        if n:
            found.append(name)
    return text, found


def find_cliches(text: str) -> list[str]:
    """Các cụm sáo rỗng xuất hiện trong text (viết thường, không trùng, theo thứ tự xuất hiện)."""
    normalized = unicodedata.normalize("NFC", text)
    return list(dict.fromkeys(m.group().lower() for m in _CLICHE_RE.finditer(normalized)))
