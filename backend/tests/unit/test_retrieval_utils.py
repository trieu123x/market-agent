import uuid

from app.agent.nodes.intent_rag import drop_irrelevant
from app.rag.retriever import RetrievedChunk, _phrase_tsquery, _word_tsquery, reciprocal_rank_fusion


def _chunk(name: str) -> RetrievedChunk:
    return RetrievedChunk(uuid.uuid5(uuid.NAMESPACE_DNS, name), uuid.uuid4(), "t", 0, name, {})


def test_rrf_prefers_items_ranked_in_both_lists():
    a, b = _chunk("a"), _chunk("b")
    fused = reciprocal_rank_fusion({"vector": [a, b], "fts": [_chunk("c"), _chunk("b")]})
    assert [x.content for x in fused] == ["b", "a", "c"]
    top = fused[0]
    assert top.ranks == {"vector": 2, "fts": 2}
    assert abs(top.score - 2 / 62) < 1e-9


def test_phrase_tsquery_uses_adjacent_syllables():
    assert _phrase_tsquery("Nghỉ việc thì trả lại?") == "nghỉ <-> việc | việc <-> thì | thì <-> trả | trả <-> lại"
    assert _phrase_tsquery("lương") == "lương"
    assert _phrase_tsquery("Giá cà-phê & | ! tăng?") == "giá <-> cà | cà <-> phê | phê <-> tăng"
    assert _phrase_tsquery("!!! ?") == ""


def test_word_tsquery_is_sanitized():
    assert _word_tsquery("Giá cà-phê 'x' & | ! tăng?") == "giá | cà | phê | tăng"
    assert _word_tsquery("!!! ?") == ""


def test_drop_irrelevant_filters_by_rerank_score_and_keeps_unscored():
    good, edge, bad, unscored = _chunk("good"), _chunk("edge"), _chunk("bad"), _chunk("unscored")
    good.rerank_score, edge.rerank_score, bad.rerank_score = 1.2, -3.0, -8.1
    kept = drop_irrelevant([good, edge, bad, unscored], min_score=-3.0)
    assert [c.content for c in kept] == ["good", "edge", "unscored"]
