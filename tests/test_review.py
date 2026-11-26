from datetime import date
from pathlib import Path

import pytest

from immigration_helper.ingestion import InstructionReader, SectionChunker
from immigration_helper.models import FormId
from immigration_helper.review import FilledForm, FormReviewer, Severity, UnreadableFormError, read_filled_form
from immigration_helper.review import i765_rules as fields
from tests.form_factory import CORRECT_CHECKED, CORRECT_TEXT, fill_i765

TODAY = date(2026, 11, 20)


@pytest.fixture(scope="module")
def reviewer() -> FormReviewer:
    # The real instructions, so every check's citation phrase is tested against the official text.
    document = InstructionReader().read(Path("data/forms/i-765instr.pdf"))
    return FormReviewer(SectionChunker().chunk(document), today=lambda: TODAY)


def review_pdf(reviewer, text=None, checked=None):
    return reviewer.review(read_filled_form(fill_i765(text, checked)))


def test_a_correctly_filled_form_has_no_issues(reviewer):
    assert review_pdf(reviewer) == []


ZIP = fields.MAILING_ADDRESS["ZIP code (5.f)"]

# Each planted mistake, and where the review must point. The values are fake but must never appear in a message.
PLANTED_MISTAKES = [
    ("two reasons for applying", None, CORRECT_CHECKED | {fields.REASON[2]}, "Part 1, Item Number 1"),
    ("no reason for applying", None, CORRECT_CHECKED - {fields.REASON[0]}, "Part 1, Item Number 1"),
    ("empty family name", {**CORRECT_TEXT, fields.FAMILY_NAME: ""}, None, "Part 2, Item Numbers 1.a. - 1.b."),
    ("empty ZIP code", {**CORRECT_TEXT, ZIP: ""}, None, "Part 2, Item Numbers 5.a. - 5.f."),
    ("4-digit ZIP code", {**CORRECT_TEXT, ZIP: "8460"}, None, "Part 2, Item Numbers 5.a. - 5.f."),
    ("A-Number with a letter", {**CORRECT_TEXT, fields.A_NUMBER: "A12345678"}, None, "Part 2, Item Number 8"),
    ("short A-Number", {**CORRECT_TEXT, fields.A_NUMBER: "1234567"}, None, "Part 2, Item Number 8"),
    ("no sex selected", None, CORRECT_CHECKED - {fields.SEX[0]}, "Part 2, Item Number 10"),
    ("two marital statuses", None, CORRECT_CHECKED | {fields.MARITAL_STATUS[3]}, "Part 2, Item Number 11"),
    ("birth date in yyyy-mm-dd", {**CORRECT_TEXT, fields.DATE_OF_BIRTH: "1990-05-14"}, None, "Part 2, Item Number 16"),
    ("impossible birth date", {**CORRECT_TEXT, fields.DATE_OF_BIRTH: "02/30/1990"}, None, "Part 2, Item Number 16"),
    ("birth date in the future", {**CORRECT_TEXT, fields.DATE_OF_BIRTH: "05/14/2099"}, None, "Part 2, Item Number 16"),
    ("empty eligibility category", {**CORRECT_TEXT, fields.CATEGORY[0]: "", fields.CATEGORY[1]: ""}, None,
     "Part 2, Item Number 27"),
    ("made-up eligibility category", {**CORRECT_TEXT, fields.CATEGORY[0]: "x"}, None, "Part 2, Item Number 27"),
    ("short phone number", {**CORRECT_TEXT, fields.DAYTIME_PHONE: "8015550"}, None, "Part 3, Item Number 3"),
    ("typed signature", {**CORRECT_TEXT, fields.SIGNATURE: "A"}, None, "Part 3, Item Numbers 7.a. - 7.b."),
    ("signature date in the future", {**CORRECT_TEXT, fields.SIGNATURE_DATE: "12/25/2026"}, None,
     "Part 3, Item Numbers 7.a. - 7.b."),
]


@pytest.mark.parametrize("text, checked, location", [m[1:] for m in PLANTED_MISTAKES], ids=[m[0] for m in PLANTED_MISTAKES])
def test_each_planted_mistake_is_found_where_it_is_and_nowhere_else(reviewer, text, checked, location):
    issues = review_pdf(reviewer, text, checked)

    assert [(issue.severity, issue.location) for issue in issues] == [(Severity.ERROR, location)]
    assert issues[0].instruction_label.startswith("Form I-765 Instructions (08/21/25), p. ")
    planted = {value for value in (text or {}).values() if len(value) > 2} - set(CORRECT_TEXT.values())
    assert not any(value in issues[0].message for value in planted)  # values are never stored in a message


def test_missing_signature_and_a_number_are_reminders_not_errors(reviewer):
    issues = review_pdf(reviewer, {**CORRECT_TEXT, fields.SIGNATURE_DATE: "", fields.A_NUMBER: ""})

    assert {(issue.severity, issue.location) for issue in issues} == {
        (Severity.WARNING, "Part 2, Item Number 8"),
        (Severity.WARNING, "Part 3, Item Numbers 7.a. - 7.b."),
    }


def test_a_blank_form_lists_errors_before_warnings(reviewer):
    issues = review_pdf(reviewer, text={}, checked=set())

    severities = [issue.severity for issue in issues]
    assert severities == sorted(severities, key=lambda severity: severity is Severity.WARNING)
    assert len([s for s in severities if s is Severity.ERROR]) == 11


def test_an_older_edition_is_a_warning(reviewer):
    form = read_filled_form(fill_i765())
    older = FilledForm(form.form, date(2022, 5, 31), form.values)

    issues = reviewer.review(older)

    assert [(issue.severity, issue.location) for issue in issues] == [(Severity.WARNING, "Form edition")]
    assert "05/31/22" in issues[0].message


@pytest.mark.parametrize("data, message", [
    (b"just some text", "isn't a PDF"),
    (Path("data/forms/i-765instr.pdf").read_bytes(), "doesn't look like a USCIS form"),
])
def test_files_that_are_not_fillable_forms_are_rejected_with_a_clear_message(data, message):
    with pytest.raises(UnreadableFormError, match=message):
        read_filled_form(data)


def test_other_forms_are_not_checked_yet(reviewer):
    form = read_filled_form(Path("data/forms/i-130.pdf").read_bytes())

    assert form.form == FormId("I-130")
    with pytest.raises(UnreadableFormError, match="can check Form I-765"):
        reviewer.review(form)
