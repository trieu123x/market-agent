"""Lọc jailbreak/prompt injection bằng regex (vòng 1 của input guardrail)."""
import re
import unicodedata

_PATTERNS = {
    "ignore_instructions": r"\b(ignore|disregard|forget)\s+(all\s+|any\s+)?(the\s+|your\s+)?"
    r"(previous|prior|above|earlier|system)\s+(instructions?|prompts?|rules?|messages?)",
    "reveal_prompt": r"\b(reveal|show|print|repeat|leak|output)\s+(me\s+)?(your|the)\s+"
    r"(system\s+prompt|hidden\s+prompt|initial\s+instructions?|instructions?)",
    "role_override": r"\b(you\s+are\s+now\s+dan|do\s+anything\s+now|developer\s+mode|jailbreak)\b",
    "vi_ignore_instructions": r"\b(bỏ\s+qua|phớt\s+lờ|quên)\s+(hết\s+|tất\s+cả\s+|mọi\s+|các\s+)?(những\s+)?"
    r"(hướng\s+dẫn|chỉ\s+dẫn|chỉ\s+thị|quy\s+tắc|lệnh)\s*(trước|phía\s+trên|ở\s+trên|hệ\s+thống)?",
    "vi_reveal_prompt": r"\b(tiết\s+lộ|in\s+ra|cho\s+(tôi|tao|mình)\s+xem)\s+"
    r"(system\s+prompt|prompt\s+hệ\s+thống|chỉ\s+thị\s+hệ\s+thống)",
    "tag_injection": r"<\s*/?\s*(system|external_context|assistant)\s*>",
}
_COMPILED = {name: re.compile(p, re.IGNORECASE) for name, p in _PATTERNS.items()}


def detect_jailbreak(text: str) -> str | None:
    """Trả về tên luật bị vi phạm, hoặc None nếu sạch."""
    normalized = unicodedata.normalize("NFC", text)
    for name, pattern in _COMPILED.items():
        if pattern.search(normalized):
            return name
    return None
