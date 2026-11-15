"""Answer-level evaluation: answer every question, judge each answer, and summarize by question style."""
from dataclasses import dataclass

from immigration_helper.answering import Answer, Answerer
from immigration_helper.evaluation.eval_set import EvalQuestion
from immigration_helper.evaluation.judge import AnswerJudge, Correctness, Support, Verdict


@dataclass(frozen=True)
class AnswerResult:
    question: EvalQuestion
    answer: Answer
    verdict: Verdict

    @property
    def is_correct(self) -> bool:
        """Answerable questions: the judge found it correct. Out-of-scope ones: the assistant declined.

        Declining an answerable question is always wrong for the user, whatever the judge says, so that rule is
        applied in code rather than left to the judge.
        """
        if self.question.target is None:
            return not self.answer.answerable
        return self.answer.answerable and self.verdict.correctness is Correctness.CORRECT

    @property
    def is_partially_correct(self) -> bool:
        return (self.question.target is not None and self.answer.answerable
                and self.verdict.correctness is Correctness.PARTIAL)


@dataclass(frozen=True)
class AnswerSummary:
    group: str  # "answerable", "plain", "jargon" or "out_of_scope"
    questions: int
    correct: float  # for out-of-scope questions: declined
    partially_correct: float
    fully_supported: float
    declined: float
    gives_advice: float


class AnswerEvaluator:
    def __init__(self, answerer: Answerer, judge: AnswerJudge):
        self._answerer = answerer
        self._judge = judge

    def evaluate_one(self, question: EvalQuestion) -> AnswerResult:
        answer = self._answerer.answer(question.text)
        reference = question.target.reference_answer if question.target else None
        return AnswerResult(question, answer, self._judge.judge(answer, reference))


def summarize_answers(results: list[AnswerResult]) -> list[AnswerSummary]:
    groups: dict[str, list[AnswerResult]] = {"answerable": [r for r in results if r.question.target]}
    for result in results:
        groups.setdefault(result.question.style.value, []).append(result)
    return [_summarize_group(name, group) for name, group in groups.items() if group]


def _summarize_group(name: str, results: list[AnswerResult]) -> AnswerSummary:
    count = len(results)

    def share(predicate) -> float:
        return sum(1 for result in results if predicate(result)) / count

    return AnswerSummary(
        group=name,
        questions=count,
        correct=share(lambda r: r.is_correct),
        partially_correct=share(lambda r: r.is_partially_correct),
        fully_supported=share(lambda r: r.verdict.support is Support.FULL),
        declined=share(lambda r: not r.answer.answerable),
        gives_advice=share(lambda r: r.verdict.gives_advice),
    )
