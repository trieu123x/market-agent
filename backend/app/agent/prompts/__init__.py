import re
from functools import lru_cache
from pathlib import Path

_DIR = Path(__file__).parent
_TAG_RE = re.compile(r"<\s*/?\s*external_context\s*>", re.IGNORECASE)


@lru_cache
def load_prompt(name: str) -> str:
    return (_DIR / f"{name}.md").read_text(encoding="utf-8")


def external_context(chunks: list[str]) -> str:
    """Bọc tài liệu ngoài trong thẻ <external_context>; bỏ thẻ giả mạo bên trong để không thoát được khỏi thẻ."""
    body = "\n\n".join(_TAG_RE.sub("", c) for c in chunks) or "(Không có tài liệu tham chiếu)"
    return f"<external_context>\n{body}\n</external_context>"
