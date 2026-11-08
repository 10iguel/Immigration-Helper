"""Keyword search with BM25: the baseline that embeddings have to beat."""
import heapq
import re

from rank_bm25 import BM25Okapi

from immigration_helper.models import Chunk
from immigration_helper.retrieval.retriever import ScoredChunk

# Keeps USCIS codes intact as tokens: "(c)(9)" -> "(c)", "(9)"; "I-765" -> "i-765"; "A-Number" -> "a-number".
_TOKEN_PATTERN = re.compile(r"\([a-z0-9]+\)|[a-z0-9]+(?:[-'][a-z0-9]+)*")


def tokenize(text: str) -> list[str]:
    return _TOKEN_PATTERN.findall(text.lower())


class KeywordRetriever:
    name = "keyword-bm25"

    def __init__(self, chunks: list[Chunk]):
        self._chunks = list(chunks)
        self._index = BM25Okapi([tokenize(chunk.search_text()) for chunk in self._chunks])

    def search(self, query: str, k: int) -> list[ScoredChunk]:
        scores = self._index.get_scores(tokenize(query))
        best = heapq.nlargest(k, range(len(scores)), key=scores.__getitem__)
        return [ScoredChunk(self._chunks[i], float(scores[i])) for i in best]
