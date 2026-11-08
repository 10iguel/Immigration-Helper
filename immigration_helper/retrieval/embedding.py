"""Semantic search: chunks and questions are embedded and compared by cosine similarity."""
import hashlib
from pathlib import Path

import chromadb
from chromadb.config import Settings

from immigration_helper.models import Chunk
from immigration_helper.retrieval.embedder import Embedder
from immigration_helper.retrieval.retriever import ScoredChunk


class EmbeddingRetriever:
    """Searches a persistent Chroma index of chunk embeddings.

    The index is reused across runs and rebuilt only when the chunks or the embedding model change,
    so chunks are paid for once, not on every evaluation run.
    """

    def __init__(self, chunks: list[Chunk], embedder: Embedder, index_dir: Path):
        self.name = f"embedding-{embedder.model}"
        self._chunks = {chunk.id: chunk for chunk in chunks}
        self._embedder = embedder
        client = chromadb.PersistentClient(path=str(index_dir), settings=Settings(anonymized_telemetry=False))
        self._collection = self._load_or_build(client, chunks)

    def search(self, query: str, k: int) -> list[ScoredChunk]:
        [vector] = self._embedder.embed([query])
        result = self._collection.query(query_embeddings=[vector], n_results=k, include=["distances"])
        return [
            ScoredChunk(self._chunks[chunk_id], 1.0 - distance)  # cosine distance -> similarity
            for chunk_id, distance in zip(result["ids"][0], result["distances"][0])
        ]

    def _load_or_build(self, client: chromadb.ClientAPI, chunks: list[Chunk]) -> chromadb.Collection:
        name = f"chunks-{self._embedder.model}"
        fingerprint = self._fingerprint(chunks)
        if name in {collection.name for collection in client.list_collections()}:
            collection = client.get_collection(name, embedding_function=None)
            if collection.metadata.get("fingerprint") == fingerprint and collection.count() == len(chunks):
                return collection
            client.delete_collection(name)

        collection = client.create_collection(
            name,
            metadata={"fingerprint": fingerprint},
            configuration={"hnsw": {"space": "cosine"}},
            embedding_function=None,
        )
        collection.add(
            ids=[chunk.id for chunk in chunks],
            embeddings=self._embedder.embed([chunk.search_text() for chunk in chunks]),
        )
        return collection

    def _fingerprint(self, chunks: list[Chunk]) -> str:
        digest = hashlib.sha256(self._embedder.model.encode())
        for chunk in chunks:
            digest.update(chunk.id.encode())
            digest.update(chunk.search_text().encode())
        return digest.hexdigest()
