"""Evaluation questions with known answers, used to measure retrieval and answer quality."""
import json
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from immigration_helper.models import Chunk, FormId


class QuestionStyle(Enum):
    PLAIN = "plain"  # everyday wording, e.g. "work permit"
    JARGON = "jargon"  # official USCIS terms, e.g. "EAD under category (c)(9)"
    OUT_OF_SCOPE = "out_of_scope"  # not answered by any loaded instructions
    CONVERSATION = "conversation"  # small talk ("thanks!"): the agent should reply without searching
    FOLLOW_UP = "follow_up"  # asked after an earlier question in the same chat, and only makes sense with it

    @property
    def needs_target(self) -> bool:
        return self not in (QuestionStyle.OUT_OF_SCOPE, QuestionStyle.CONVERSATION)


@dataclass(frozen=True)
class AnswerTarget:
    """The passage that answers a question, identified by phrases from the official text.

    Phrases (rather than chunk IDs) keep the labels valid for any chunking strategy: a chunk is
    relevant if it belongs to the target's form and contains any of the phrases.
    """

    id: str
    form: FormId
    answer_phrases: tuple[str, ...]
    reference_answer: str

    def __post_init__(self) -> None:
        if not self.answer_phrases:
            raise ValueError(f"Answer target {self.id} needs at least one answer phrase")

    def is_answered_by(self, chunk: Chunk) -> bool:
        return chunk.form == self.form and any(chunk.contains(phrase) for phrase in self.answer_phrases)

    def relevant_chunk_ids(self, chunks: list[Chunk]) -> list[str]:
        return [chunk.id for chunk in chunks if self.is_answered_by(chunk)]


@dataclass(frozen=True)
class EvalQuestion:
    id: str
    text: str
    style: QuestionStyle
    target: AnswerTarget | None  # None for out-of-scope and conversation messages
    previous_question: str | None = None  # follow-ups: asked first, in the same chat

    def __post_init__(self) -> None:
        if (self.target is not None) != self.style.needs_target:
            raise ValueError(f"Question {self.id}: only out-of-scope and conversation messages have no answer target")
        if (self.previous_question is not None) != (self.style is QuestionStyle.FOLLOW_UP):
            raise ValueError(f"Question {self.id}: only follow-up questions have a previous question")


class EvalSetStore:
    """Loads the evaluation set from JSON.

    Each answer target is asked twice, in plain and in jargon wording, so the pair isolates the
    effect of vocabulary on retrieval. Question IDs are ``<target id>-<style>``.
    """

    def __init__(self, path: Path):
        self._path = path

    def load(self) -> list[EvalQuestion]:
        with self._path.open(encoding="utf-8") as file:
            data = json.load(file)
        questions = [question for record in data["targets"] for question in self._target_questions(record)]
        questions += [
            EvalQuestion(record["id"], record["question"], QuestionStyle.OUT_OF_SCOPE, target=None)
            for record in data["out_of_scope"]
        ]
        questions += [
            EvalQuestion(record["id"], record["message"], QuestionStyle.CONVERSATION, target=None)
            for record in data.get("conversation", [])
        ]
        questions += [
            EvalQuestion(record["id"], record["question"], QuestionStyle.FOLLOW_UP, self._target(record),
                         previous_question=record["previous_question"])
            for record in data.get("follow_ups", [])
        ]
        return questions

    @classmethod
    def _target_questions(cls, record: dict) -> list[EvalQuestion]:
        target = cls._target(record)
        return [
            EvalQuestion(f"{target.id}-{style}", text, QuestionStyle(style), target)
            for style, text in record["questions"].items()
        ]

    @staticmethod
    def _target(record: dict) -> AnswerTarget:
        return AnswerTarget(
            id=record["id"],
            form=FormId(record["form"]),
            answer_phrases=tuple(record["answer_phrases"]),
            reference_answer=record["reference_answer"],
        )
