"""The search interface shared by every retrieval strategy."""
from dataclasses import dataclass
from typing import Protocol

from immigration_helper.models import Chunk


@dataclass(frozen=True)
class ScoredChunk:
    chunk: Chunk
    score: float  # higher is more relevant; only comparable within one retriever


class Retriever(Protocol):
    name: str

    def search(self, query: str, k: int) -> list[ScoredChunk]:
        """Return the ``k`` most relevant chunks, best first."""
        ...
