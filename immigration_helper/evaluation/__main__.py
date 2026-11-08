"""Evaluation commands, run from the project root:

    python -m immigration_helper.evaluation validate    # every answer target matches a chunk
    python -m immigration_helper.evaluation retrieval   # score retrievers, save results/retrieval-*.json
"""
import argparse
import json
from datetime import datetime
from pathlib import Path

from immigration_helper.evaluation.eval_set import EvalSetStore, QuestionStyle
from immigration_helper.evaluation.retrieval_eval import QuestionResult, RetrievalEvaluator, summarize
from immigration_helper.ingestion import ChunkStore
from immigration_helper.models import Chunk
from immigration_helper.retrieval import EmbeddingRetriever, KeywordRetriever, OpenAIEmbedder, Retriever

_RETRIEVERS = ("keyword", "embedding")


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate the USCIS helper on the evaluation set.")
    parser.add_argument("--eval-set", type=Path, default=Path("data/eval/eval_set.json"))
    parser.add_argument("--chunks", type=Path, default=Path("data/index/chunks.jsonl"))
    commands = parser.add_subparsers(dest="command", required=True)

    commands.add_parser("validate", help="check that every answer target matches at least one chunk")

    retrieval = commands.add_parser("retrieval", help="score retrievers with Recall@k and MRR")
    retrieval.add_argument("--retrievers", nargs="+", choices=_RETRIEVERS, default=list(_RETRIEVERS))
    retrieval.add_argument("--embedding-model", default="text-embedding-3-small")
    retrieval.add_argument("--index-dir", type=Path, default=Path("data/index/chroma"))
    retrieval.add_argument("--k", type=int, default=10, help="chunks retrieved per question")
    retrieval.add_argument("--output-dir", type=Path, default=Path("results"))

    args = parser.parse_args()
    questions = EvalSetStore(args.eval_set).load()
    chunks = ChunkStore(args.chunks).load()
    if args.command == "validate":
        validate(questions, chunks)
    else:
        evaluate_retrieval(args, questions, chunks)


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
    embedder = OpenAIEmbedder(args.embedding_model) if "embedding" in args.retrievers else None

    runs: dict[str, list[QuestionResult]] = {}
    for retriever in build_retrievers(args, chunks, embedder):
        runs[retriever.name] = evaluator.evaluate(retriever)

    summaries = [summary for name, results in runs.items() for summary in summarize(name, results)]
    print(f"{'retriever':<34} {'style':<7} {'n':>3} {'R@1':>6} {'R@5':>6} {'MRR':>6}")
    for s in summaries:
        print(f"{s.retriever:<34} {s.style:<7} {s.questions:>3} {s.recall_at_1:>6.2f} {s.recall_at_5:>6.2f} {s.mrr:>6.2f}")
    for name, results in runs.items():
        misses = [result.question.id for result in results if not result.hit_at(5)]
        print(f"\n{name} misses at 5 ({len(misses)}): {', '.join(misses) or 'none'}")

    usage = embedder.usage() if embedder else None
    if usage:
        print(f"\nEmbedding tokens this run: {usage.tokens} (${usage.cost_usd:.6f})")

    output = args.output_dir / f"retrieval-{datetime.now():%Y%m%d-%H%M%S}.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps({
        "k": args.k,
        "embedding_model": args.embedding_model if embedder else None,
        "embedding_tokens": usage.tokens if usage else 0,
        "embedding_cost_usd": usage.cost_usd if usage else 0.0,
        "summaries": [vars(summary) for summary in summaries],
        "questions": {name: [question_record(result) for result in results] for name, results in runs.items()},
    }, indent=2), encoding="utf-8")
    print(f"Saved {output}")


def build_retrievers(args: argparse.Namespace, chunks: list[Chunk], embedder: OpenAIEmbedder | None) -> list[Retriever]:
    retrievers: list[Retriever] = []
    if "keyword" in args.retrievers:
        retrievers.append(KeywordRetriever(chunks))
    if embedder:
        retrievers.append(EmbeddingRetriever(chunks, embedder, args.index_dir))
    return retrievers


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
