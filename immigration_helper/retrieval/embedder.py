"""Turns text into vectors, keeping count of tokens so every run's cost is measured."""
from dataclasses import dataclass
from typing import Protocol

from openai import OpenAI

# USD per 1M input tokens (OpenAI pricing page); update if prices change.
_USD_PER_MILLION_TOKENS = {
    "text-embedding-3-small": 0.02,
    "text-embedding-3-large": 0.13,
}
_BATCH_SIZE = 100


@dataclass(frozen=True)
class EmbeddingUsage:
    tokens: int
    cost_usd: float


class Embedder(Protocol):
    model: str

    def embed(self, texts: list[str]) -> list[list[float]]: ...

    def usage(self) -> EmbeddingUsage: ...


class OpenAIEmbedder:
    """Embeds with the OpenAI API; reads the key from the OPENAI_API_KEY environment variable."""

    def __init__(self, model: str = "text-embedding-3-small", client: OpenAI | None = None):
        if model not in _USD_PER_MILLION_TOKENS:
            raise ValueError(f"No price known for embedding model {model!r}")
        self.model = model
        self._client = client or OpenAI()
        self._tokens = 0

    def embed(self, texts: list[str]) -> list[list[float]]:
        vectors: list[list[float]] = []
        for start in range(0, len(texts), _BATCH_SIZE):
            response = self._client.embeddings.create(model=self.model, input=texts[start:start + _BATCH_SIZE])
            self._tokens += response.usage.total_tokens
            vectors.extend(item.embedding for item in response.data)
        return vectors

    def usage(self) -> EmbeddingUsage:
        return EmbeddingUsage(self._tokens, self._tokens * _USD_PER_MILLION_TOKENS[self.model] / 1_000_000)
