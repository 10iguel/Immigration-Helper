"""The `answers` evaluation command: answer every question, grade it with the judge, and save the results."""
import argparse
import json
from datetime import datetime
from pathlib import Path

from immigration_helper import config
from immigration_helper.answering import Answerer
from immigration_helper.answering.pipeline import build_retriever
from immigration_helper.chat_model import NO_USAGE, OpenAIChatModel
from immigration_helper.evaluation.answer_eval import AnswerEvaluator, AnswerResult, summarize_answers
from immigration_helper.evaluation.eval_set import EvalQuestion
from immigration_helper.evaluation.judge import AnswerJudge
from immigration_helper.models import Chunk
from immigration_helper.retrieval import OpenAIEmbedder, QueryRewriter


def add_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--passages", type=int, default=config.ANSWER_PASSAGES, help="passages shown to the answering model")
    parser.add_argument("--form-filter", action=argparse.BooleanOptionalAction, default=config.FORM_FILTER,
                        help="search only forms named in the question")
    parser.add_argument("--chat-model", default=config.CHAT_MODEL, help="model that rewrites and answers")
    parser.add_argument("--judge-model", default=config.JUDGE_MODEL)
    parser.add_argument("--embedding-model", default=config.EMBEDDING_MODEL)
    parser.add_argument("--index-dir", type=Path, default=config.VECTOR_INDEX_DIR)
    parser.add_argument("--questions", nargs="+", help="only these question IDs")
    parser.add_argument("--limit", type=int, help="only the first N questions, for quick checks")
    parser.add_argument("--output-dir", type=Path, default=config.RESULTS_DIR)


def run(args: argparse.Namespace, questions: list[EvalQuestion], chunks: list[Chunk]) -> None:
    selected = [question for question in questions if not args.questions or question.id in args.questions]
    selected = selected[:args.limit]

    chat_model = OpenAIChatModel(args.chat_model)
    embedder = OpenAIEmbedder(args.embedding_model)
    rewriter = QueryRewriter(chat_model)
    retriever = build_retriever(chunks, embedder, rewriter, args.index_dir, args.form_filter)
    evaluator = AnswerEvaluator(Answerer(retriever, chat_model, args.passages), AnswerJudge(OpenAIChatModel(args.judge_model)))

    results: list[AnswerResult] = []
    for number, question in enumerate(selected, start=1):
        result = evaluator.evaluate_one(question)
        results.append(result)
        print(f"[{number}/{len(selected)}] {question.id}: {_outcome(result)}, support {result.verdict.support.value}"
              + (", ADVICE" if result.verdict.gives_advice else ""))

    summaries = summarize_answers(results)
    print(f"\n{'group':<13} {'n':>3} {'correct':>8} {'partial':>8} {'supported':>10} {'declined':>9} {'advice':>7}")
    for s in summaries:
        print(f"{s.group:<13} {s.questions:>3} {s.correct:>8.2f} {s.partially_correct:>8.2f} "
              f"{s.fully_supported:>10.2f} {s.declined:>9.2f} {s.gives_advice:>7.2f}")

    answer_usage = sum((result.answer.usage for result in results), NO_USAGE)
    judge_usage = sum((result.verdict.usage for result in results), NO_USAGE)
    answering_cost = answer_usage.cost_usd + rewriter.usage().cost_usd + embedder.usage().cost_usd
    print(f"\nAnswering: ${answering_cost:.4f} (${answering_cost / len(results):.5f} per question); "
          f"judging: ${judge_usage.cost_usd:.4f} (${judge_usage.cost_usd / len(results):.5f} per question)")

    output = args.output_dir / f"answers-{datetime.now():%Y%m%d-%H%M%S}.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps({
        "chat_model": args.chat_model,
        "judge_model": args.judge_model,
        "passages": args.passages,
        "form_filter": args.form_filter,
        "answering_cost_usd": answering_cost,
        "judging_cost_usd": judge_usage.cost_usd,
        "summaries": [vars(summary) for summary in summaries],
        "questions": [_record(result, rewriter) for result in results],
    }, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Saved {output}")


def _outcome(result: AnswerResult) -> str:
    if result.question.target is None:
        return "declined (correct)" if result.is_correct else "ANSWERED out-of-scope question"
    return result.verdict.correctness.value


def _record(result: AnswerResult, rewriter: QueryRewriter) -> dict:
    question, answer, verdict = result.question, result.answer, result.verdict
    return {
        "id": question.id,
        "style": question.style.value,
        "question": question.text,
        "search_query": rewriter.rewrite(question.text),  # cached, no extra call
        "reference_answer": question.target.reference_answer if question.target else None,
        "answer": answer.text,
        "answerable": answer.answerable,
        "passage_ids": [chunk.id for chunk in answer.passages],
        "citations": [citation.label for citation in answer.citations],
        "rejected_citation_ids": list(answer.rejected_citation_ids),
        "verdict": {
            "correctness": verdict.correctness.value,
            "support": verdict.support.value,
            "gives_advice": verdict.gives_advice,
            "unsupported_claims": list(verdict.unsupported_claims),
            "reasoning": verdict.reasoning,
        },
        "is_correct": result.is_correct,
        "answer_cost_usd": answer.usage.cost_usd,
        "judge_cost_usd": verdict.usage.cost_usd,
    }
