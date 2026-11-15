"""Evaluation commands, run from the project root:

    python -m immigration_helper.evaluation validate    # every answer target matches a chunk
    python -m immigration_helper.evaluation retrieval   # score retrievers, save results/retrieval-*.json
    python -m immigration_helper.evaluation answers     # answer and judge every question, save results/answers-*.json
"""
import argparse
import json
from datetime import datetime
from pathlib import Path

from immigration_helper import config
from immigration_helper.chat_model import OpenAIChatModel
from immigration_helper.evaluation import answers_command
from immigration_helper.evaluation.eval_set import EvalSetStore, QuestionStyle
from immigration_helper.evaluation.retrieval_eval import QuestionResult, RetrievalEvaluator, summarize
from immigration_helper.ingestion import ChunkStore
from immigration_helper.models import Chunk
from immigration_helper.retrieval import (
    EmbeddingRetriever,
    FormFilterRetriever,
    HybridRetriever,
    KeywordRetriever,
    OpenAIEmbedder,
    QueryRewriter,
    Retriever,
    RewritingRetriever,
)

# A base retriever ("hybrid" fuses keyword and embedding search) wrapped by modifiers in the order written:
# "+rewrite" searches with the rewritten question ("+original" keeps the original words too), and "+formfilter"
# keeps only passages from forms named in the query it receives. So "embedding+rewrite+original+formfilter"
# filters on the user's own words, while "embedding+formfilter+rewrite+original" filters on the rewrite.
_RETRIEVERS = (
    "keyword",
    "embedding",
    "hybrid",
    "keyword+rewrite",
    "keyword+rewrite+original",
    "embedding+rewrite",
    "embedding+rewrite+original",
    "hybrid+rewrite",
    "hybrid+rewrite+original",
    "embedding+formfilter",
    "embedding+rewrite+original+formfilter",
    "embedding+formfilter+rewrite+original",
)


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate the USCIS helper on the evaluation set.")
    parser.add_argument("--eval-set", type=Path, default=config.EVAL_SET_PATH)
    parser.add_argument("--chunks", type=Path, default=config.CHUNKS_PATH)
    commands = parser.add_subparsers(dest="command", required=True)

    commands.add_parser("validate", help="check that every answer target matches at least one chunk")

    retrieval = commands.add_parser("retrieval", help="score retrievers with Recall@k and MRR")
    retrieval.add_argument("--retrievers", nargs="+", choices=_RETRIEVERS, default=list(_RETRIEVERS))
    retrieval.add_argument("--embedding-model", default=config.EMBEDDING_MODEL)
    retrieval.add_argument("--chat-model", default=config.CHAT_MODEL, help="model used for query rewriting")
    retrieval.add_argument("--index-dir", type=Path, default=config.VECTOR_INDEX_DIR)
    retrieval.add_argument("--k", type=int, default=10, help="chunks retrieved per question")
    retrieval.add_argument("--output-dir", type=Path, default=config.RESULTS_DIR)

    answers_command.add_arguments(
        commands.add_parser("answers", help="answer every question and grade the answers with an LLM judge")
    )

    args = parser.parse_args()
    questions = EvalSetStore(args.eval_set).load()
    chunks = ChunkStore(args.chunks).load()
    if args.command == "validate":
        validate(questions, chunks)
    elif args.command == "retrieval":
        evaluate_retrieval(args, questions, chunks)
    else:
        answers_command.run(args, questions, chunks)


def validate(questions, chunks: list[Chunk]) -> None:
    targets = {question.target.id: question.target for question in questions if question.target}
    unmatched = []
    for target in targets.values():
        relevant = target.relevant_chunk_ids(chunks)
        print(f"{target.id} ({target.form}): {', '.join(relevant) or 'NO MATCH'}")
        if not relevant:
            unmatched.append(target.id)

    counts = {style: sum(q.style is style for q in questions) for style in QuestionStyle}
    print(f"\n{len(questions)} questions: " + ", ".join(f"{n} {style.value}" for style, n in counts.items()))
    if unmatched:
        raise SystemExit(f"Answer phrases match no chunk for: {', '.join(unmatched)}")


def evaluate_retrieval(args: argparse.Namespace, questions, chunks: list[Chunk]) -> None:
    evaluator = RetrievalEvaluator(questions, chunks, k=args.k)
    factory = _RetrieverFactory(args, chunks)

    runs: dict[str, list[QuestionResult]] = {}
    for name in args.retrievers:
        retriever = factory.build(name)
        runs[retriever.name] = evaluator.evaluate(retriever)

    summaries = [summary for name, results in runs.items() for summary in summarize(name, results)]
    print(f"{'retriever':<50} {'style':<7} {'n':>3} {'R@1':>6} {'R@5':>6} {'MRR':>6}")
    for s in summaries:
        print(f"{s.retriever:<50} {s.style:<7} {s.questions:>3} {s.recall_at_1:>6.2f} {s.recall_at_5:>6.2f} {s.mrr:>6.2f}")
    for name, results in runs.items():
        misses = [result.question.id for result in results if not result.hit_at(5)]
        print(f"\n{name} misses at 5 ({len(misses)}): {', '.join(misses) or 'none'}")

    embedding_usage = factory.embedder.usage() if factory.embedder else None
    rewrite_usage = factory.rewriter.usage() if factory.rewriter else None
    if embedding_usage:
        print(f"\nEmbedding tokens this run: {embedding_usage.tokens} (${embedding_usage.cost_usd:.6f})")
    if rewrite_usage:
        print(f"Rewriting tokens this run: {rewrite_usage.input_tokens} input + {rewrite_usage.output_tokens} output "
              f"(${rewrite_usage.cost_usd:.6f})")

    output = args.output_dir / f"retrieval-{datetime.now():%Y%m%d-%H%M%S}.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps({
        "k": args.k,
        "embedding_model": args.embedding_model if embedding_usage else None,
        "embedding_tokens": embedding_usage.tokens if embedding_usage else 0,
        "embedding_cost_usd": embedding_usage.cost_usd if embedding_usage else 0.0,
        "rewrite_model": args.chat_model if rewrite_usage else None,
        "rewrite_usage": vars(rewrite_usage) if rewrite_usage else None,
        "rewrites": factory.rewriter.rewrites() if factory.rewriter else {},
        "summaries": [vars(summary) for summary in summaries],
        "questions": {name: [question_record(result) for result in results] for name, results in runs.items()},
    }, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Saved {output}")


class _RetrieverFactory:
    """Builds retrievers by name, sharing one embedding index and one rewrite cache across them."""

    def __init__(self, args: argparse.Namespace, chunks: list[Chunk]):
        self._args = args
        self._chunks = chunks
        self._bases: dict[str, Retriever] = {}
        needs_embeddings = self._needs("embedding") or self._needs("hybrid")
        self.embedder = OpenAIEmbedder(args.embedding_model) if needs_embeddings else None
        self.rewriter = QueryRewriter(OpenAIChatModel(args.chat_model)) if self._needs("rewrite") else None

    def build(self, name: str) -> Retriever:
        """Wraps the base retriever with each modifier in the order written, innermost first."""
        base_name, *modifiers = name.split("+")
        retriever = self._base(base_name)
        for position, modifier in enumerate(modifiers):
            if modifier == "rewrite":
                keep_original = modifiers[position + 1:position + 2] == ["original"]
                retriever = RewritingRetriever(retriever, self.rewriter, keep_original)
            elif modifier == "formfilter":
                retriever = FormFilterRetriever(retriever, {chunk.form for chunk in self._chunks})
        return retriever

    def _base(self, name: str) -> Retriever:
        if name not in self._bases:
            if name == "keyword":
                self._bases[name] = KeywordRetriever(self._chunks)
            elif name == "embedding":
                self._bases[name] = EmbeddingRetriever(self._chunks, self.embedder, self._args.index_dir)
            else:
                self._bases[name] = HybridRetriever([self._base("keyword"), self._base("embedding")])
        return self._bases[name]

    def _needs(self, part: str) -> bool:
        return any(part in name.split("+") for name in self._args.retrievers)


def question_record(result: QuestionResult) -> dict:
    return {
        "id": result.question.id,
        "style": result.question.style.value,
        "question": result.question.text,
        "first_relevant_rank": result.first_relevant_rank(),
        "retrieved_ids": list(result.retrieved_ids),
        "relevant_ids": sorted(result.relevant_ids),
    }


if __name__ == "__main__":
    main()
