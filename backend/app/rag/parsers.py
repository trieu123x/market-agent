"""Chuyển PDF / DOCX / TXT / HTML về Markdown thống nhất trước khi chunk."""
import io
import logging
import re

import pymupdf
from bs4 import BeautifulSoup
from docx import Document as DocxDocument
from docx.table import Table

from app.core.config import get_settings

log = logging.getLogger(__name__)

PDF_MAGIC = b"%PDF-"
ZIP_MAGIC = b"PK\x03\x04"


def _normalize(text: str) -> str:
    """Làm sạch text: bỏ ký tự null, chuẩn hóa xuống dòng, gộp dòng trống thừa."""
    text = text.replace("\x00", "").replace("\r\n", "\n")
    text = re.sub(r"[ \t]+\n", "\n", text)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def _has_meaningful_images(page: "pymupdf.Page", min_px: int) -> bool:
    # get_images(full=True) tuple: (xref, smask, width, height, ...)
    """Trang có ảnh đủ lớn để đáng OCR (bỏ qua icon/logo nhỏ) hay không."""
    return any(min(img[2], img[3]) >= min_px for img in page.get_images(full=True))


def _page_text(page: "pymupdf.Page", ocr_ok: bool) -> tuple[str, bool]:
    """Trả (text, ocr_ok). ocr_ok chuyển False nếu Tesseract không dùng được để khỏi thử lại mọi trang."""
    cfg = get_settings()
    if ocr_ok and cfg.ocr_enabled and _has_meaningful_images(page, cfg.ocr_min_image_px):
        try:
            # full=False: chỉ OCR vùng ảnh, giữ nguyên text gốc rồi gộp theo thứ tự đọc.
            tp = page.get_textpage_ocr(language=cfg.ocr_language, dpi=cfg.ocr_dpi, full=False)
            return page.get_text("text", sort=True, textpage=tp).strip(), True
        except Exception as exc:  # thiếu tesseract/tessdata, ảnh lỗi...
            log.warning("OCR lỗi ở trang %d (%s) – dùng text gốc, tắt OCR cho file này", page.number + 1, exc)
            ocr_ok = False
    text = page.get_text("text", sort=True).strip()
    if not text and page.get_images():
        log.warning("PDF page %d chỉ có ảnh nhưng OCR không khả dụng, bỏ qua", page.number + 1)
    return text, ocr_ok


def pdf_to_markdown(data: bytes) -> str:
    """PDF → text theo từng trang, OCR các trang có ảnh rồi gộp lại."""
    pages = []
    ocr_ok = True
    with pymupdf.open(stream=data, filetype="pdf") as doc:
        for page in doc:
            text, ocr_ok = _page_text(page, ocr_ok)
            if text:
                pages.append(text)
    return _normalize("\n\n".join(pages))


def _ocr_image(blob: bytes) -> str:
    """OCR một ảnh rời (png/jpg/...): đổi sang PDF 1 trang rồi dùng Tesseract của PyMuPDF."""
    cfg = get_settings()
    with pymupdf.open(stream=blob) as img:
        if min(img[0].rect.width, img[0].rect.height) < cfg.ocr_min_image_px:
            return ""
        pdf_bytes = img.convert_to_pdf()
    with pymupdf.open(stream=pdf_bytes, filetype="pdf") as pdf:
        page = pdf[0]
        tp = page.get_textpage_ocr(language=cfg.ocr_language, dpi=cfg.ocr_dpi, full=True)
        return page.get_text("text", sort=True, textpage=tp).strip()


def _docx_images_text(doc, element, ocr_ok: bool) -> tuple[list[str], bool]:
    """OCR các ảnh nhúng trong một paragraph/ô bảng. Trả (các đoạn text, ocr_ok)."""
    if not ocr_ok or not get_settings().ocr_enabled:
        return [], ocr_ok
    out: list[str] = []
    for rid in element.xpath(".//a:blip/@r:embed"):
        try:
            text = _ocr_image(doc.part.related_parts[rid].blob)
        except Exception as exc:  # thiếu tesseract, định dạng emf/wmf không hỗ trợ...
            log.warning("OCR ảnh DOCX lỗi (%s) – bỏ qua ảnh", exc)
            if "tesseract" in str(exc).lower() or "tessdata" in str(exc).lower():
                return out, False
            continue
        if text:
            out.append(text)
    return out, ocr_ok


def _docx_images_text_in_table(doc, table: Table, ocr_ok: bool) -> list[str]:
    """OCR ảnh nằm trong một bảng DOCX."""
    return _docx_images_text(doc, table._element, ocr_ok)[0]


def docx_to_markdown(data: bytes) -> str:
    """DOCX → Markdown (heading, list, bảng) kèm text OCR từ ảnh nhúng."""
    doc = DocxDocument(io.BytesIO(data))
    lines: list[str] = []
    ocr_ok = True
    for block in doc.iter_inner_content():
        if isinstance(block, Table):
            for row in block.rows:
                cells = [c.text.strip().replace("\n", " ") for c in row.cells]
                lines.append("| " + " | ".join(cells) + " |")
            lines.append("")
            for text in _docx_images_text_in_table(doc, block, ocr_ok):
                lines += [text, ""]
            continue
        img_texts, ocr_ok = _docx_images_text(doc, block._element, ocr_ok)
        text = block.text.strip()
        if not text and not img_texts:
            continue
        if not text:
            lines += ["\n\n".join(img_texts), ""]
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
        for t in img_texts:
            lines += [t, ""]
    return _normalize("\n".join(lines))


def txt_to_markdown(data: bytes) -> str:
    """TXT → text, tự thử UTF-8 rồi cp1258."""
    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = data.decode("cp1258", errors="replace")
    return _normalize(text)


_BLOCK_TAGS = ["h1", "h2", "h3", "h4", "h5", "h6", "p", "li", "pre", "blockquote", "td", "th"]


def html_to_markdown(html: bytes | str) -> str:
    """HTML → Markdown, bỏ thẻ nhiễu (script, nav, footer...) và giữ heading/list."""
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


_TOC_TITLE_RE = re.compile(r"^\s*(?:#{1,6}\s*)?(?:\*\*)?(?:mục\s+lục|table\s+of\s+contents|contents)(?:\*\*)?\s*:?\s*$", re.I)
# "Tên mục ....... 12" / "Tên mục … 12" / "Tên mục<TAB>12" (Word TOC)
_TOC_LEADER_RE = re.compile(r"^(?!#)\S.*?(?:\s*[.·_]{3,}\s*|\s*…+\s*|\t+)\d{1,4}$")
# Chỉ dùng ngay sau tiêu đề "Mục lục": "Tên mục 12" hoặc dòng bảng "| Tên mục | 12 |"
_TOC_LOOSE_RE = re.compile(r"^(?!#)\S.{0,140}\s\d{1,4}$")
_TOC_TABLE_RE = re.compile(r"^\|.*\|\s*\d{1,4}\s*\|$")
_PAGE_NUMBER_RE = re.compile(r"^\d{1,4}$")


def _toc_block_end(lines: list[str], start: int, loose: bool) -> tuple[int, int]:
    """Quét block mục lục từ `start`. Trả (chỉ số ngay sau entry cuối, số entry).

    Entry đầu tiên có dấu dẫn thì các entry sau cũng phải có, để không nuốt dòng nội dung tình cờ kết thúc
    bằng số (vd. "...không quá 48")."""
    i = end = start
    entries = wrapped = 0
    while i < len(lines):
        line = lines[i].strip()
        if not line or (entries and _PAGE_NUMBER_RE.match(line)):  # dòng trống / số trang ở footer PDF
            i += 1
            continue
        is_leader = bool(_TOC_LEADER_RE.match(line))
        if is_leader and not entries:
            loose = False
        if is_leader or (loose and (_TOC_LOOSE_RE.match(line) or _TOC_TABLE_RE.match(line))):
            entries += 1
            wrapped = 0
            i = end = i + 1
            continue
        # Tên mục dài bị ngắt dòng (PDF) hoặc nhãn cột "Trang": chỉ tính nếu dòng sau là entry
        if not line.startswith("#") and len(line) <= 120 and wrapped < 2:
            wrapped += 1
            i += 1
            continue
        break
    return end, entries


def strip_table_of_contents(md: str) -> str:
    """Bỏ mục lục khỏi Markdown: nó chỉ lặp lại tiêu đề kèm số trang, làm nhiễu retrieval.

    - Có tiêu đề "Mục lục"/"Contents": bỏ tiêu đề + các entry sau đó (cần >= 2 entry).
    - Không có tiêu đề: chỉ bỏ chuỗi >= 3 entry có dấu dẫn (..... / … / tab) liền nhau.
    """
    lines = md.split("\n")
    out: list[str] = []
    i = 0
    while i < len(lines):
        if _TOC_TITLE_RE.match(lines[i]):
            end, entries = _toc_block_end(lines, i + 1, loose=True)
            if entries >= 2:
                i = end
                continue
        elif _TOC_LEADER_RE.match(lines[i].strip()):
            end, entries = _toc_block_end(lines, i, loose=False)
            if entries >= 3:
                i = end
                continue
        out.append(lines[i])
        i += 1
    return _normalize("\n".join(out))


def _parse(file_type: str, data: bytes, content_type: str) -> str:
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


def parse_to_markdown(file_type: str, data: bytes, content_type: str = "") -> str:
    """Chọn parser theo loại file (PDF/DOCX/TXT/URL), trả về Markdown đã bỏ mục lục."""
    return strip_table_of_contents(_parse(file_type, data, content_type))
