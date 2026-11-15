"""LLM-as-judge: a stronger model grades each answer against the passages it used and a reference answer.

A different, stronger model than the one answering (gpt-4.1 vs. gpt-4.1-mini) reduces self-preference bias.
"""
from dataclasses import dataclass
from enum import Enum

from immigration_helper.answering import Answer
from immigration_helper.answering.prompt import format_passages
from immigration_helper.chat_model import ChatModel, ChatUsage


class Support(Enum):
    FULL = "full"  # every factual claim is stated in the passages
    PARTIAL = "partial"  # some claims are not
    NONE = "none"  # the main claim is not


class Correctness(Enum):
    CORRECT = "correct"
    PARTIAL = "partial"  # incomplete or vague on the main point, but not wrong
    INCORRECT = "incorrect"
    NOT_APPLICABLE = "not_applicable"  # no reference answer (out-of-scope question)


@dataclass(frozen=True)
class Verdict:
    reasoning: str
    unsupported_claims: tuple[str, ...]
    support: Support
    correctness: Correctness
    gives_advice: bool
    usage: ChatUsage


JUDGE_PROMPT = """\
You grade answers from an assistant that answers questions about USCIS form instructions. The assistant must use \
only the passages it was given. Be strict and specific.

You receive the question, the passages the assistant was given, the assistant's answer, and a reference answer \
written by a person from the official instructions (or a note that the loaded instructions don't answer the \
question). Write your reasoning first, then grade:

1. support: Judged against the passages only, not the reference answer. Is every factual claim in the answer \
stated in the passages? "full" if all are, "partial" if some are not, "none" if the main claim is not. List each \
unsupported claim in "unsupported_claims". Saying that the instructions don't cover something is not a factual \
claim, so an answer that only declines has "full" support.
2. correctness: Compare with the reference answer on the main point the question asks about, judging against the \
reference only, even if the passages lack the information. "correct" if the answer gives that main point and \
doesn't contradict the reference; "partial" if it is incomplete or vague on the main point but not wrong; \
"incorrect" if it contradicts the reference or misses the main point. If there is a reference answer and the \
assistant says the instructions don't cover the question, that is "incorrect": the information exists in the \
instructions and the assistant failed to find it. Extra correct details are fine. Use "not_applicable" when there \
is no reference answer.
3. gives_advice: true if the answer tells the person what they should decide or do in their own case, beyond \
describing what the instructions say or require. Suggesting they check uscis.gov or ask an immigration attorney \
is not advice."""

JUDGE_SCHEMA = {
    "type": "object",
    "properties": {
        "reasoning": {"type": "string"},
        "unsupported_claims": {"type": "array", "items": {"type": "string"}},
        "support": {"type": "string", "enum": [support.value for support in Support]},
        "correctness": {"type": "string", "enum": [correctness.value for correctness in Correctness]},
        "gives_advice": {"type": "boolean"},
    },
    "required": ["reasoning", "unsupported_claims", "support", "correctness", "gives_advice"],
    "additionalProperties": False,
}

_NO_REFERENCE = "None. The loaded instructions do not answer this question; a good answer says so."


class AnswerJudge:
    def __init__(self, chat_model: ChatModel):
        self._chat_model = chat_model

    def judge(self, answer: Answer, reference_answer: str | None) -> Verdict:
        messages = [
            {"role": "system", "content": JUDGE_PROMPT},
            {"role": "user", "content": (
                f"Question: {answer.question}\n\n"
                f"Passages the assistant was given:\n\n{format_passages(list(answer.passages))}\n\n"
                f"Assistant's answer:\n{answer.text}\n\n"
                f"Reference answer: {reference_answer or _NO_REFERENCE}"
            )},
        ]
        result = self._chat_model.complete_json(messages, JUDGE_SCHEMA, schema_name="answer_verdict")
        return Verdict(
            reasoning=result.content["reasoning"],
            unsupported_claims=tuple(result.content["unsupported_claims"]),
            support=Support(result.content["support"]),
            correctness=Correctness(result.content["correctness"]),
            gives_advice=result.content["gives_advice"],
            usage=result.usage,
        )
