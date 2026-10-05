"""Che PII trong prompt trước khi gửi cho LLM (email, thẻ ngân hàng, CCCD, số điện thoại VN)."""
import re

EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
CARD_RE = re.compile(r"(?<!\d)(?:\d[ -]?){12,18}\d(?!\d)")
CCCD_RE = re.compile(r"(?<!\d)\d{12}(?!\d)")
PHONE_RE = re.compile(r"(?<![\d+])(?:\+?84|0)(?:[ .-]?\d){9}(?!\d)")


def _luhn_ok(digits: str) -> bool:
    """Kiểm tra checksum Luhn để tránh che nhầm dãy số thường."""
    total = 0
    for i, ch in enumerate(reversed(digits)):
        d = int(ch)
        if i % 2:
            d = d * 2 - 9 if d > 4 else d * 2
        total += d
    return total % 10 == 0


def mask_pii(text: str) -> tuple[str, list[str]]:
    """Trả về (text đã che, danh sách loại PII tìm thấy)."""
    found: list[str] = []

    def sub(pattern: re.Pattern, label: str, text_: str, check=None) -> str:
        def repl(m: re.Match) -> str:
            if check and not check(m.group()):
                return m.group()
            found.append(label)
            return f"[{label}]"

        return pattern.sub(repl, text_)

    text = sub(EMAIL_RE, "EMAIL", text)
    text = sub(CARD_RE, "CARD", text, lambda s: _luhn_ok(re.sub(r"\D", "", s)))
    text = sub(CCCD_RE, "ID_NUMBER", text)
    text = sub(PHONE_RE, "PHONE", text)
    return text, sorted(set(found))
