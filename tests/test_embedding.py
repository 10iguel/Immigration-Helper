from immigration_helper.retrieval import EmbeddingRetriever, EmbeddingUsage
from tests.factories import make_chunk

VOCABULARY = ("work", "travel", "photo")


class FakeEmbedder:
    """Counts vocabulary words, so texts about the same topic get similar vectors."""

    model = "fake-model"

    def __init__(self):
        self.texts_embedded = 0

    def embed(self, texts: list[str]) -> list[list[float]]:
        self.texts_embedded += len(texts)
        return [[float(text.lower().count(word)) + 0.01 for word in VOCABULARY] for text in texts]

    def usage(self) -> EmbeddingUsage:
        return EmbeddingUsage(tokens=0, cost_usd=0.0)


CHUNKS = [
    make_chunk("Apply for permission to work.", chunk_id="I-765-0001"),
    make_chunk("Get a document before you travel abroad.", chunk_id="I-765-0002"),
    make_chunk("Attach a passport photo.", chunk_id="I-765-0003"),
]


def test_search_returns_most_similar_chunk_first(tmp_path):
    retriever = EmbeddingRetriever(CHUNKS, FakeEmbedder(), tmp_path)

    results = retriever.search("Can I travel?", k=2)

    assert results[0].chunk.id == "I-765-0002"
    assert results[0].score > results[1].score


def test_index_is_reused_when_chunks_are_unchanged(tmp_path):
    EmbeddingRetriever(CHUNKS, FakeEmbedder(), tmp_path)
    embedder = FakeEmbedder()

    EmbeddingRetriever(CHUNKS, embedder, tmp_path)

    assert embedder.texts_embedded == 0


def test_index_is_rebuilt_when_chunks_change(tmp_path):
    EmbeddingRetriever(CHUNKS, FakeEmbedder(), tmp_path)
    changed = CHUNKS[:2] + [make_chunk("Attach two photos.", chunk_id="I-765-0003")]
    embedder = FakeEmbedder()

    retriever = EmbeddingRetriever(changed, embedder, tmp_path)

    assert embedder.texts_embedded == len(changed)
    assert retriever.search("photo", k=1)[0].chunk.text == "Attach two photos."
