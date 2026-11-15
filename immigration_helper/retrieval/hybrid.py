"""Hybrid search: combine several retrievers' rankings with reciprocal rank fusion (RRF).

Keyword search is precise on exact codes like "(c)(9)"; embeddings understand paraphrases. RRF merges their
rankings using only rank positions, because BM25 scores and cosine similarities are not on the same scale.
"""
import heapq
from collections import defaultdict

from immigration_helper.models import Chunk
from immigration_helper.retrieval.retriever import Retriever, ScoredChunk

_RRF_K = 60  # standard constant (Cormack et al., 2009); keeps one list's top rank from dominating the fusion


class HybridRetriever:
    def __init__(self, retrievers: list[Retriever], candidates: int = 50):
        if not retrievers:
            raise ValueError("Hybrid search needs at least one retriever")
        self._retrievers = retrievers
        self._candidates = candidates  # results taken from each retriever before fusing
        self.name = "hybrid-rrf"

    def search(self, query: str, k: int) -> list[ScoredChunk]:
        scores: dict[str, float] = defaultdict(float)
        chunks: dict[str, Chunk] = {}
        for retriever in self._retrievers:
            for rank, result in enumerate(retriever.search(query, max(k, self._candidates)), start=1):
                scores[result.chunk.id] += 1.0 / (_RRF_K + rank)
                chunks[result.chunk.id] = result.chunk
        best = heapq.nlargest(k, scores, key=scores.__getitem__)
        return [ScoredChunk(chunks[chunk_id], scores[chunk_id]) for chunk_id in best]
