"""The `grading-sheet` and `agreement` commands: grade saved answers by hand and compare with the judge."""
import argparse
from pathlib import Path

from immigration_helper.evaluation.human_check import (
    HUMAN_GRADES,
    default_sheet_path,
    load_saved_answers,
    measure_agreement,
    select_for_grading,
    write_sheet,
)


def add_sheet_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("results", type=Path, help="a saved run, results/answers-*.json")
    parser.add_argument("--count", type=int, default=15, help="answers to grade")
    parser.add_argument("--seed", type=int, default=0, help="which random answers are picked")
    parser.add_argument("--sheet", type=Path, help="where to write the sheet (default: results/grading-*.csv)")


def add_agreement_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("results", type=Path, help="the saved run the sheet was made from")
    parser.add_argument("--sheet", type=Path, help="the graded sheet (default: results/grading-*.csv)")


def run_sheet(args: argparse.Namespace) -> None:
    sheet = args.sheet or default_sheet_path(args.results)
    answers = select_for_grading(load_saved_answers(args.results), args.count, args.seed)
    write_sheet(answers, sheet)
    print(f"Wrote {len(answers)} answers to {sheet}\n"
          f"Fill in your_grade with {', '.join(grade.value for grade in HUMAN_GRADES)} "
          "(the README has the rules), then run the agreement command.")


def run_agreement(args: argparse.Namespace) -> None:
    sheet = args.sheet or default_sheet_path(args.results)
    agreement = measure_agreement(load_saved_answers(args.results), sheet)
    graded = len(agreement.graded)
    print(f"Graded {graded} answers" + (f" ({len(agreement.ungraded_ids)} still blank)" if agreement.ungraded_ids else ""))
    print(f"Same grade as the judge:          {agreement.exact_rate:.0%} "
          f"({sum(answer.agrees for answer in agreement.graded)}/{graded})")
    print(f"Same 'correct or not' decision:   {agreement.correct_rate:.0%} "
          f"({sum(answer.agrees_on_correct for answer in agreement.graded)}/{graded})")
    for answer in agreement.disagreements():
        print(f"\n{answer.saved.question_id}: you {answer.human_grade.value}, judge {answer.saved.judge_grade.value}")
        if answer.note:
            print(f"   your note: {answer.note}")
        print(f"   judge: {answer.saved.judge_reasoning}")
