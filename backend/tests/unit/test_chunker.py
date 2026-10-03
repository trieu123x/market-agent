from app.rag.chunker import count_tokens, split_markdown


def test_short_text_single_chunk():
    chunks = split_markdown("# Tiêu đề\n\nMột đoạn ngắn.", 800, 150)
    assert len(chunks) == 1
    assert chunks[0].heading == "Tiêu đề"


def test_chunks_respect_size_and_overlap():
    paragraphs = [f"Đoạn số {i}. " + "Nội dung marketing về sản phẩm cà phê rang xay. " * 12 for i in range(40)]
    chunks = split_markdown("\n\n".join(paragraphs), 800, 150)
    assert len(chunks) > 3
    assert all(c.token_count <= 800 + 10 for c in chunks)  # +separator
    for prev, nxt in zip(chunks, chunks[1:]):
        # đoạn đầu của chunk sau là đoạn cuối của chunk trước (overlap)
        first_para = nxt.content.split("\n\n")[0]
        assert first_para in prev.content


def test_oversized_paragraph_is_hard_split():
    text = "từkhóa " * 3000  # một đoạn, không có dấu câu
    chunks = split_markdown(text, 800, 150)
    assert len(chunks) > 1
    assert all(count_tokens(c.content) <= 820 for c in chunks)


def test_empty_text():
    assert split_markdown("   \n\n  ", 800, 150) == []
