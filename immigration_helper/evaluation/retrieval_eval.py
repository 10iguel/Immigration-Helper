"""Scores a retriever on the evaluation set: Recall@k and mean reciprocal rank, by question style."""
from dataclasses import dataclass

from immigration_helper.evaluation.eval_set import EvalQuestion, QuestionStyle
from immigration_helper.models import Chunk
from immigration_helper.retrieval import Retriever


@dataclass(frozen=True)
class QuestionResult:
    question: EvalQuestion
    retrieved_ids: tuple[str, ...]
    relevant_ids: frozenset[str]

    def first_relevant_rank(self) -> int | None:
        """1-based rank of the first relevant chunk, or None if none was retrieved."""
        for rank, chunk_id in enumerate(self.retrieved_ids, start=1):
            if chunk_id in self.relevant_ids:
                return rank
        return None

    def hit_at(self, k: int) -> bool:
        rank = self.first_relevant_rank()
        return rank is not None and rank <= k

    def reciprocal_rank(self) -> float:
        rank = self.first_relevant_rank()
        return 1.0 / rank if rank else 0.0


@dataclass(frozen=True)
class RetrievalSummary:
    retriever: str
    style: str  # "all", "plain" or "jargon"
    questions: int
    recall_at_1: float
    recall_at_5: float
    mrr: float


class RetrievalEvaluator:
    """Runs every plain and jargon question through a retriever. Out-of-scope and conversation messages have
    nothing to find, and follow-ups only make sense with the earlier question, so they're judged on answers only."""

    def __init__(self, questions: list[EvalQuestion], chunks: list[Chunk], k: int = 10):
        self._questions = [question for question in questions
                           if question.style in (QuestionStyle.PLAIN, QuestionStyle.JARGON)]
        self._relevant = {
            question.target.id: frozenset(question.target.relevant_chunk_ids(chunks)) for question in self._questions
        }
        self._k = k

    def evaluate(self, retriever: Retriever) -> list[QuestionResult]:
        return [
            QuestionResult(
                question=question,
                retrieved_ids=tuple(result.chunk.id for result in retriever.search(question.text, self._k)),
                relevant_ids=self._relevant[question.target.id],
            )
            for question in self._questions
        ]


def summarize(retriever_name: str, results: list[QuestionResult]) -> list[RetrievalSummary]:
    """One summary over all questions, then one per question style."""
    groups = {"all": results}
    for result in results:
        groups.setdefault(result.question.style.value, []).append(result)
    return [_summarize_group(retriever_name, style, group) for style, group in groups.items()]


def _summarize_group(retriever_name: str, style: str, results: list[QuestionResult]) -> RetrievalSummary:
    count = len(results)
    return RetrievalSummary(
        retriever=retriever_name,
        style=style,
        questions=count,
        recall_at_1=sum(result.hit_at(1) for result in results) / count,
        recall_at_5=sum(result.hit_at(5) for result in results) / count,
        mrr=sum(result.reciprocal_rank() for result in results) / count,
    )
