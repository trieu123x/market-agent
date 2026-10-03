import io

import pymupdf
from docx import Document as DocxDocument

from app.rag.parsers import docx_to_markdown, html_to_markdown, parse_to_markdown, pdf_to_markdown, txt_to_markdown


def test_pdf_to_markdown():
    doc = pymupdf.open()
    doc.new_page().insert_text((72, 72), "Brand guideline page one")
    doc.new_page().insert_text((72, 72), "Second page content")
    md = pdf_to_markdown(doc.tobytes())
    assert "Brand guideline page one" in md and "Second page content" in md


def test_docx_to_markdown_headings_lists_tables():
    d = DocxDocument()
    d.add_heading("Chiến dịch Tết", level=1)
    d.add_paragraph("Mục tiêu tăng nhận diện.")
    d.add_paragraph("Kênh Facebook", style="List Bullet")
    t = d.add_table(rows=1, cols=2)
    t.rows[0].cells[0].text = "KPI"
    t.rows[0].cells[1].text = "10%"
    buf = io.BytesIO()
    d.save(buf)
    md = docx_to_markdown(buf.getvalue())
    assert "# Chiến dịch Tết" in md
    assert "- Kênh Facebook" in md
    assert "| KPI | 10% |" in md


def test_txt_utf8_bom():
    assert txt_to_markdown("﻿Xin chào\r\n\r\n\r\n\r\nthế giới".encode()) == "Xin chào\n\nthế giới"


def test_html_strips_boilerplate():
    html = "<html><body><nav>Menu</nav><article><h2>Tiêu đề</h2><p>Nội dung <b>chính</b></p>" \
           "<script>alert(1)</script></article><footer>©</footer></body></html>"
    md = html_to_markdown(html)
    assert md == "## Tiêu đề\n\nNội dung chính"


def test_url_pdf_content_dispatch():
    doc = pymupdf.open()
    doc.new_page().insert_text((72, 72), "Remote pdf")
    assert "Remote pdf" in parse_to_markdown("URL", doc.tobytes(), "application/pdf")
