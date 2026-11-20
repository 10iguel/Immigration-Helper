"""Answer-level evaluation: answer every question the way users get answers, judge each answer, and summarize by
question style."""
from dataclasses import dataclass

from immigration_helper.answering import Answer, PriorMessage, ReplyKind
from immigration_helper.evaluation.eval_set import EvalQuestion, QuestionStyle
from immigration_helper.evaluation.judge import AnswerJudge, Correctness, Support, Verdict
from immigration_helper.history import QuestionAnswerer

# What the judge compares small talk against: there is no reference answer, only an expectation.
SMALL_TALK_REFERENCE = ("None: this message is small talk, not a question about the instructions. A good reply is "
                        "one or two friendly sentences with no immigration facts.")


@dataclass(frozen=True)
class AnswerResult:
    question: EvalQuestion
    answer: Answer
    verdict: Verdict
    cost_usd: float  # answering this question, including the earlier question of a follow-up

    @property
    def searched(self) -> bool:
        return bool(self.answer.searches)

    @property
    def is_correct(self) -> bool:
        """Answerable questions: the judge found the answer correct. Out-of-scope questions: the assistant searched,
        then declined. Small talk: a conversation reply without searching.

        These rules don't need judgment, so they're applied in code: declining an answerable question is always
        wrong, and replying to an immigration question without searching skips the grounding this project needs.
        """
        if self.question.style is QuestionStyle.CONVERSATION:
            return self.answer.kind is ReplyKind.CONVERSATION and not self.searched
        if self.question.target is None:
            return self.answer.kind is ReplyKind.NOT_COVERED and self.searched
        return self.answer.answerable and self.verdict.correctness is Correctness.CORRECT

    @property
    def is_partially_correct(self) -> bool:
        return (self.question.target is not None and self.answer.answerable
                and self.verdict.correctness is Correctness.PARTIAL)


@dataclass(frozen=True)
class AnswerSummary:
    group: str  # "answerable", or a question style
    questions: int
    correct: float  # out of scope: searched and declined; conversation: replied without searching
    partially_correct: float
    fully_supported: float
    declined: float
    searched: float
    gives_advice: float


class AnswerEvaluator:
    def __init__(self, assistant: QuestionAnswerer, judge: AnswerJudge):
        self._assistant = assistant
        self._judge = judge

    def evaluate_one(self, question: EvalQuestion) -> AnswerResult:
        history: tuple[PriorMessage, ...] = ()
        cost = 0.0
        if question.previous_question:
            first = self._assistant.ask(question.previous_question)
            history = (PriorMessage("user", question.previous_question), PriorMessage("assistant", first.answer.text))
            cost += first.cost_usd
        reply = self._assistant.ask(question.text, history)
        verdict = self._judge.judge(reply.answer, _reference_for(question))
        return AnswerResult(question, reply.answer, verdict, cost + reply.cost_usd)


def _reference_for(question: EvalQuestion) -> str | None:
    if question.target:
        return question.target.reference_answer
    return SMALL_TALK_REFERENCE if question.style is QuestionStyle.CONVERSATION else None


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
        searched=share(lambda r: r.searched),
        gives_advice=share(lambda r: r.verdict.gives_advice),
    )
