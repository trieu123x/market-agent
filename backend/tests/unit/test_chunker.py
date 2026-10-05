from app.rag.chunker import count_tokens, split_markdown


def test_short_text_single_chunk():
    chunks = split_markdown("# Tiêu đề\n\nMột đoạn ngắn.", 800, 150)
    assert len(chunks) == 1
    assert chunks[0].headings == ["Tiêu đề"]


def test_chunks_respect_size_and_overlap():
    paragraphs = [f"Đoạn số {i}. " + "Nội dung marketing về sản phẩm cà phê rang xay. " * 12 for i in range(40)]
    chunks = split_markdown("\n\n".join(paragraphs), 800, 150)
    assert len(chunks) > 3
    assert all(c.token_count <= 800 for c in chunks)
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


def test_overlap_never_starts_mid_word():
    words = "người lao động nghĩa vụ bảo mật thông tin khuyến khích chuyên nghiệp".split()
    paragraphs = [" ".join(words[(i + j) % len(words)] for j in range(400)) for i in range(6)]
    text = "\n\n".join(paragraphs)
    vocabulary = set(text.split())
    chunks = split_markdown(text, 800, 150)
    assert len(chunks) > 1
    for c in chunks:
        assert c.content.split()[0] in vocabulary, c.content[:40]
