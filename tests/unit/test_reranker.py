from app.retrieval.reranker import spread_across_sources


def chunks(*source_ids: str) -> list[dict[str, str]]:
    """Chunks in retrieval order, one per given source id."""
    return [{"source_id": sid, "content": f"c{n}"} for n, sid in enumerate(source_ids)]


def kept(candidates, limit=3, per_source=2) -> list[str]:
    return [c["source_id"] for c in spread_across_sources(candidates, limit, per_source)]


def test_keeps_the_nearest_when_no_source_repeats():
    assert kept(chunks("a", "b", "c")) == ["a", "b", "c"]


def test_skips_a_source_that_hit_the_cap():
    # "a" is nearest three times, but only two of its chunks may be used.
    assert kept(chunks("a", "a", "a", "b")) == ["a", "a", "b"]


def test_stops_at_the_limit():
    assert len(kept(chunks("a", "b", "c", "d"))) == 3


def test_returns_fewer_when_the_cap_leaves_nothing():
    # Only one source exists, so the cap is the binding constraint.
    assert kept(chunks("a", "a", "a", "a")) == ["a", "a"]


def test_no_candidates_is_no_result():
    assert spread_across_sources([], 3, 2) == []
