"""The retrieval setup used for answering, shared by the ask command and the answer evaluation."""
from pathlib import Path

from immigration_helper.models import Chunk
from immigration_helper.retrieval import (
    Embedder,
    EmbeddingRetriever,
    FormFilterRetriever,
    QueryRewriter,
    Retriever,
    RewritingRetriever,
)


def build_retriever(
    chunks: list[Chunk], embedder: Embedder, rewriter: QueryRewriter, index_dir: Path, form_filter: bool = False
) -> Retriever:
    """Embedding search with the original question plus its rewrite, the best setup in the retrieval evaluation.

    The optional form filter sees only the user's words, never the rewrite, which can name the wrong form.
    """
    retriever: Retriever = RewritingRetriever(EmbeddingRetriever(chunks, embedder, index_dir), rewriter, keep_original=True)
    if form_filter:
        retriever = FormFilterRetriever(retriever, known_forms={chunk.form for chunk in chunks})
    return retriever
