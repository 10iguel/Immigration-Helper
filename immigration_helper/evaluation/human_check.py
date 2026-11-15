"""Checking the judge against a person: grade a sample of saved answers by hand, then measure agreement.

The grading sheet leaves out the judge's grade so the person isn't anchored by it (blind grading). Only answerable
questions are sampled: out-of-scope questions are graded by a rule in code, not by the judge.
"""
import csv
import json
import random
from dataclasses import dataclass
from pathlib import Path

from immigration_helper.evaluation.judge import Correctness

HUMAN_GRADES = (Correctness.CORRECT, Correctness.PARTIAL, Correctness.INCORRECT)
_COLUMNS = ("id", "question", "reference_answer", "answer", "your_grade", "your_note")
_ENCODING = "utf-8-sig"  # the byte-order mark makes Excel read the file as UTF-8


@dataclass(frozen=True)
class SavedAnswer:
    """One answerable question from a saved `answers` run (results/answers-*.json)."""
    question_id: str
    question: str
    reference_answer: str
    answer: str
    judge_grade: Correctness
    judge_reasoning: str

    @classmethod
    def from_record(cls, record: dict) -> "SavedAnswer":
        # A decline counts as incorrect for an answerable question, the same rule the evaluation applies in code.
        judge_grade = Correctness(record["verdict"]["correctness"]) if record["answerable"] else Correctness.INCORRECT
        return cls(record["id"], record["question"], record["reference_answer"], record["answer"],
                   judge_grade, record["verdict"]["reasoning"])


@dataclass(frozen=True)
class GradedAnswer:
    saved: SavedAnswer
    human_grade: Correctness
    note: str

    @property
    def agrees(self) -> bool:
        return self.human_grade is self.saved.judge_grade

    @property
    def agrees_on_correct(self) -> bool:
        """Agreement on the headline metric, which only counts "correct"."""
        return (self.human_grade is Correctness.CORRECT) == (self.saved.judge_grade is Correctness.CORRECT)


@dataclass(frozen=True)
class Agreement:
    graded: tuple[GradedAnswer, ...]
    ungraded_ids: tuple[str, ...]

    @property
    def exact_rate(self) -> float:
        return sum(answer.agrees for answer in self.graded) / len(self.graded)

    @property
    def correct_rate(self) -> float:
        return sum(answer.agrees_on_correct for answer in self.graded) / len(self.graded)

    def disagreements(self) -> list[GradedAnswer]:
        return [answer for answer in self.graded if not answer.agrees]


def load_saved_answers(results_path: Path) -> list[SavedAnswer]:
    records = json.loads(results_path.read_text(encoding="utf-8"))["questions"]
    return [SavedAnswer.from_record(record) for record in records if record["reference_answer"] is not None]


def default_sheet_path(results_path: Path) -> Path:
    return results_path.with_name(results_path.stem.replace("answers-", "grading-") + ".csv")


def select_for_grading(answers: list[SavedAnswer], count: int, seed: int) -> list[SavedAnswer]:
    """Every answer the judge did not grade correct, filled up with random correct ones, in shuffled order.

    Almost all answers are graded correct, so a purely random sample would rarely test the judge's other grades.
    The shuffle keeps the grader from guessing the judge's grade from an answer's position.
    """
    rng = random.Random(seed)
    not_correct = [answer for answer in answers if answer.judge_grade is not Correctness.CORRECT]
    correct = [answer for answer in answers if answer.judge_grade is Correctness.CORRECT]
    sample = not_correct[:count] + rng.sample(correct, min(len(correct), max(0, count - len(not_correct))))
    rng.shuffle(sample)
    return sample


def write_sheet(answers: list[SavedAnswer], path: Path) -> None:
    if path.exists():
        raise FileExistsError(f"{path} already exists; delete it first if you want a new sheet (its grades are lost)")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding=_ENCODING) as file:
        writer = csv.writer(file)
        writer.writerow(_COLUMNS)
        for answer in answers:
            writer.writerow((answer.question_id, answer.question, answer.reference_answer, answer.answer, "", ""))


def measure_agreement(answers: list[SavedAnswer], sheet_path: Path) -> Agreement:
    by_id = {answer.question_id: answer for answer in answers}
    graded, ungraded = [], []
    with sheet_path.open(newline="", encoding=_ENCODING) as file:
        for row in csv.DictReader(file):
            if row["id"] not in by_id:
                raise ValueError(f"{sheet_path}: question {row['id']} is not in the results file")
            grade = row["your_grade"].strip().lower()
            if not grade:
                ungraded.append(row["id"])
                continue
            graded.append(GradedAnswer(by_id[row["id"]], _parse_grade(grade, row["id"]), row["your_note"].strip()))
    if not graded:
        raise ValueError(f"{sheet_path}: no grades yet; fill in the your_grade column first")
    return Agreement(tuple(graded), tuple(ungraded))


def _parse_grade(grade: str, question_id: str) -> Correctness:
    allowed = {correctness.value: correctness for correctness in HUMAN_GRADES}
    if grade not in allowed:
        raise ValueError(f"{question_id}: grade {grade!r} must be one of {', '.join(allowed)}")
    return allowed[grade]
