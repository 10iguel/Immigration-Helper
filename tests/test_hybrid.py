import pytest

from immigration_helper.retrieval import HybridRetriever, ScoredChunk
from tests.factories import make_chunk

CHUNKS = {chunk_id: make_chunk(chunk_id, chunk_id=chunk_id) for chunk_id in ("I-765-0001", "I-765-0002", "I-765-0003")}


class RankedRetriever:
    """Returns the given chunk IDs in order, with made-up scores on its own scale."""

    def __init__(self, name: str, ranking: list[str], scale: float):
        self.name = name
        self._ranking = ranking
        self._scale = scale

    def search(self, query: str, k: int) -> list[ScoredChunk]:
        return [ScoredChunk(CHUNKS[chunk_id], self._scale / rank)
                for rank, chunk_id in enumerate(self._ranking[:k], start=1)]


def test_chunk_ranked_well_by_both_retrievers_beats_one_ranked_first_by_only_one():
    keyword = RankedRetriever("keyword", ["I-765-0001", "I-765-0002"], scale=25.0)  # BM25-like scores
    embedding = RankedRetriever("embedding", ["I-765-0003", "I-765-0002"], scale=0.8)  # cosine-like scores

    results = HybridRetriever([keyword, embedding]).search("question", k=3)

    assert results[0].chunk.id == "I-765-0002"
    assert results[0].score == pytest.approx(2 / 62)


def test_fusion_ignores_score_scales_and_returns_k_results():
    loud = RankedRetriever("loud", ["I-765-0001"], scale=1000.0)
    quiet = RankedRetriever("quiet", ["I-765-0003"], scale=0.001)

    results = HybridRetriever([loud, quiet]).search("question", k=1)

    assert len(results) == 1
    assert results[0].score == pytest.approx(1 / 61)


def test_hybrid_needs_a_retriever():
    with pytest.raises(ValueError):
        HybridRetriever([])
