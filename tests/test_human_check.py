import csv
import json

import pytest

from immigration_helper.evaluation.human_check import (
    default_sheet_path,
    load_saved_answers,
    measure_agreement,
    select_for_grading,
    write_sheet,
)
from immigration_helper.evaluation.judge import Correctness


def record(question_id: str, correctness: str, answerable: bool = True, reference: str | None = "Yes.") -> dict:
    return {"id": question_id, "question": f"Question {question_id}?", "reference_answer": reference,
            "answer": "Yes, you must.", "answerable": answerable,
            "verdict": {"correctness": correctness, "reasoning": f"reasoning for {question_id}"}}


@pytest.fixture
def results_path(tmp_path):
    records = [record(f"t{n:02d}", "correct") for n in range(1, 11)]
    records += [record("t11", "partial"), record("t12", "correct", answerable=False),
                record("o01", "not_applicable", answerable=False, reference=None)]
    path = tmp_path / "answers-run.json"
    path.write_text(json.dumps({"questions": records}), encoding="utf-8")
    return path


def fill_grades(sheet, grades: dict[str, str]) -> None:
    with sheet.open(newline="", encoding="utf-8-sig") as file:
        rows = list(csv.DictReader(file))
    for row in rows:
        row["your_grade"] = grades.get(row["id"], "")
    with sheet.open("w", newline="", encoding="utf-8-sig") as file:
        writer = csv.DictWriter(file, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def test_out_of_scope_questions_are_left_out_and_a_decline_counts_as_incorrect(results_path):
    answers = {answer.question_id: answer for answer in load_saved_answers(results_path)}

    assert "o01" not in answers
    assert answers["t12"].judge_grade is Correctness.INCORRECT


def test_sample_keeps_every_answer_not_graded_correct(results_path):
    sample = select_for_grading(load_saved_answers(results_path), count=5, seed=0)

    ids = {answer.question_id for answer in sample}
    assert len(sample) == 5
    assert {"t11", "t12"} <= ids


def test_sheet_hides_the_judge_grade_and_is_not_overwritten(results_path):
    sheet = default_sheet_path(results_path)
    write_sheet(load_saved_answers(results_path), sheet)

    content = sheet.read_text(encoding="utf-8-sig")
    assert sheet.name == "grading-run.csv"
    assert "judge" not in content.splitlines()[0]
    assert "reasoning for" not in content
    with pytest.raises(FileExistsError):
        write_sheet([], sheet)


def test_agreement_counts_exact_and_correct_or_not_matches(results_path):
    answers = load_saved_answers(results_path)
    sheet = default_sheet_path(results_path)
    write_sheet(answers, sheet)
    fill_grades(sheet, {"t01": "correct", "t02": "partial", "t11": "incorrect", "t12": "Incorrect"})

    agreement = measure_agreement(answers, sheet)

    assert len(agreement.graded) == 4
    assert agreement.exact_rate == 0.5  # t01 and t12 match
    assert agreement.correct_rate == 0.75  # only t02 differs on correct-or-not
    assert [answer.saved.question_id for answer in agreement.disagreements()] == ["t02", "t11"]
    assert len(agreement.ungraded_ids) == len(answers) - 4


def test_agreement_rejects_unknown_grades(results_path):
    answers = load_saved_answers(results_path)
    sheet = default_sheet_path(results_path)
    write_sheet(answers, sheet)
    fill_grades(sheet, {"t01": "good"})

    with pytest.raises(ValueError, match="must be one of"):
        measure_agreement(answers, sheet)
