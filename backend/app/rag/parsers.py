"""Chuyển PDF / DOCX / TXT / HTML về Markdown thống nhất trước khi chunk."""
import io
import logging
import re

import pymupdf
from bs4 import BeautifulSoup
from docx import Document as DocxDocument
from docx.table import Table

log = logging.getLogger(__name__)

PDF_MAGIC = b"%PDF-"
ZIP_MAGIC = b"PK\x03\x04"


def _normalize(text: str) -> str:
    text = text.replace("\x00", "").replace("\r\n", "\n")
    text = re.sub(r"[ \t]+\n", "\n", text)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def pdf_to_markdown(data: bytes) -> str:
    pages = []
    with pymupdf.open(stream=data, filetype="pdf") as doc:
        for page in doc:
            text = page.get_text("text", sort=True).strip()
            if not text and page.get_images():
                # OCR chưa triển khai (để buffer ngày 5) – trang scan sẽ bị bỏ qua.
                log.warning("PDF page %d chỉ có ảnh, bỏ qua vì chưa bật OCR", page.number + 1)
            if text:
                pages.append(text)
    return _normalize("\n\n".join(pages))


def docx_to_markdown(data: bytes) -> str:
    doc = DocxDocument(io.BytesIO(data))
    lines: list[str] = []
    for block in doc.iter_inner_content():
        if isinstance(block, Table):
            for row in block.rows:
                cells = [c.text.strip().replace("\n", " ") for c in row.cells]
                lines.append("| " + " | ".join(cells) + " |")
            lines.append("")
            continue
        text = block.text.strip()
        if not text:
            continue
        style = (block.style.name if block.style is not None else "") or ""
        if style.startswith("Heading") and style[-1:].isdigit():
            lines.append("#" * min(int(style[-1]), 6) + " " + text)
        elif style == "Title":
            lines.append("# " + text)
        elif style.startswith("List"):
            lines.append("- " + text)
        else:
            lines.append(text)
        lines.append("")
    return _normalize("\n".join(lines))


def txt_to_markdown(data: bytes) -> str:
    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = data.decode("cp1258", errors="replace")
    return _normalize(text)


_BLOCK_TAGS = ["h1", "h2", "h3", "h4", "h5", "h6", "p", "li", "pre", "blockquote", "td", "th"]


def html_to_markdown(html: bytes | str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "noscript", "nav", "footer", "header", "aside", "form", "svg", "iframe"]):
        tag.decompose()
    root = soup.find("article") or soup.find("main") or soup.body or soup
    lines: list[str] = []
    for el in root.find_all(_BLOCK_TAGS):
        # Bỏ phần tử lồng trong phần tử block khác để tránh lặp nội dung.
        if el.find_parent(_BLOCK_TAGS):
            continue
        text = " ".join(el.get_text(" ", strip=True).split())
        if not text:
            continue
        if el.name[0] == "h" and el.name[1:].isdigit():
            lines.append("#" * int(el.name[1:]) + " " + text)
        elif el.name == "li":
            lines.append("- " + text)
        else:
            lines.append(text)
        lines.append("")
    if not lines:
        return _normalize(root.get_text("\n", strip=True))
    return _normalize("\n".join(lines))


def parse_to_markdown(file_type: str, data: bytes, content_type: str = "") -> str:
    if file_type == "PDF":
        return pdf_to_markdown(data)
    if file_type == "DOCX":
        return docx_to_markdown(data)
    if file_type == "TXT":
        return txt_to_markdown(data)
    if file_type == "URL":
        ctype = content_type.split(";")[0].strip().lower()
        if ctype == "application/pdf" or data.startswith(PDF_MAGIC):
            return pdf_to_markdown(data)
        if ctype.startswith("text/plain"):
            return txt_to_markdown(data)
        return html_to_markdown(data)
    raise ValueError(f"Unsupported file type: {file_type}")
