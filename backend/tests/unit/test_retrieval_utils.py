import uuid

from app.rag.embedder import HashEmbedder
from app.rag.retriever import RetrievedChunk, _to_tsquery_text, reciprocal_rank_fusion


def _chunk(name: str) -> RetrievedChunk:
    return RetrievedChunk(uuid.uuid5(uuid.NAMESPACE_DNS, name), uuid.uuid4(), "t", 0, name, {})


def test_rrf_prefers_items_ranked_in_both_lists():
    a, b, c = _chunk("a"), _chunk("b"), _chunk("c")
    fused = reciprocal_rank_fusion({"vector": [a, b], "fts": [_chunk("c"), _chunk("b")]})
    assert [x.content for x in fused] == ["b", "a", "c"]
    top = fused[0]
    assert top.ranks == {"vector": 2, "fts": 2}
    assert abs(top.score - 2 / 62) < 1e-9


def test_tsquery_text_is_sanitized():
    assert _to_tsquery_text("Giá cà-phê 'x' & | ! tăng?") == "giá | cà | phê | tăng"
    assert _to_tsquery_text("!!! ?") == ""


async def test_hash_embedder_deterministic_and_normalized():
    e = HashEmbedder()
    [v1, v2] = await e.embed(["cà phê sữa", "cà phê sữa"])
    assert v1 == v2 and len(v1) == 1536
    assert abs(sum(x * x for x in v1) - 1) < 1e-9
