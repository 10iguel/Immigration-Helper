import pytest

from immigration_helper.evaluation import AnswerTarget, EvalQuestion, QuestionStyle
from immigration_helper.evaluation.retrieval_eval import QuestionResult, RetrievalEvaluator, summarize
from immigration_helper.models import FormId
from immigration_helper.retrieval import ScoredChunk
from tests.factories import make_chunk

CHUNKS = [
    make_chunk("Submit photos.", chunk_id="I-765-0001"),
    make_chunk("File under category (c)(9).", chunk_id="I-765-0002"),
]
TARGET = AnswerTarget("t01", FormId("I-765"), ("category (c)(9)",), "File under (c)(9).")
PLAIN = EvalQuestion("t01-plain", "Can I work while I wait?", QuestionStyle.PLAIN, TARGET)
JARGON = EvalQuestion("t01-jargon", "How do I file under (c)(9)?", QuestionStyle.JARGON, TARGET)
OUT_OF_SCOPE = EvalQuestion("o01", "How do I become a citizen?", QuestionStyle.OUT_OF_SCOPE, None)


class FixedRetriever:
    """Returns the jargon question's answer first and the plain question's answer second."""

    name = "fixed"

    def search(self, query: str, k: int) -> list[ScoredChunk]:
        order = CHUNKS[::-1] if "(c)(9)" in query else CHUNKS
        return [ScoredChunk(chunk, 1.0) for chunk in order[:k]]


def test_question_result_ranks_and_reciprocal_rank():
    result = QuestionResult(PLAIN, ("I-765-0001", "I-765-0002"), frozenset({"I-765-0002"}))

    assert result.first_relevant_rank() == 2
    assert not result.hit_at(1)
    assert result.hit_at(5)
    assert result.reciprocal_rank() == 0.5


def test_question_result_with_no_relevant_chunk_scores_zero():
    result = QuestionResult(PLAIN, ("I-765-0001",), frozenset({"I-765-0002"}))

    assert result.first_relevant_rank() is None
    assert result.reciprocal_rank() == 0.0


def test_evaluator_skips_out_of_scope_questions():
    results = RetrievalEvaluator([PLAIN, JARGON, OUT_OF_SCOPE], CHUNKS).evaluate(FixedRetriever())

    assert [result.question.id for result in results] == ["t01-plain", "t01-jargon"]


def test_summaries_split_by_style():
    results = RetrievalEvaluator([PLAIN, JARGON], CHUNKS).evaluate(FixedRetriever())

    summaries = {summary.style: summary for summary in summarize("fixed", results)}

    assert summaries["jargon"].recall_at_1 == 1.0
    assert summaries["plain"].recall_at_1 == 0.0
    assert summaries["all"].mrr == pytest.approx(0.75)
