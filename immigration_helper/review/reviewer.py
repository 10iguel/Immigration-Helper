"""Runs a form's checks and attaches the instruction passage behind each one."""
from collections.abc import Callable
from datetime import date

from immigration_helper.answering import Citation
from immigration_helper.models import Chunk, FormId
from immigration_helper.review.filled_form import FilledForm, Issue, Severity
from immigration_helper.review.i765_rules import Rule, i765_rules
from immigration_helper.review.pdf_form import UnreadableFormError

I765 = FormId("I-765")


class FormReviewer:
    """Deterministic checks (no AI): the same form always gets the same result, and every problem cites the
    instruction passage it comes from."""

    def __init__(self, chunks: list[Chunk], today: Callable[[], date] = date.today):
        instructions = [chunk for chunk in chunks if chunk.form == I765]
        if not instructions:
            raise ValueError("The Form I-765 instructions aren't loaded, so forms can't be checked")
        self._rules = {I765: i765_rules(instructions[0].edition, today)}
        # Resolved once at startup, so a phrase that no longer matches the instructions fails loudly, not silently.
        self._labels = {rule.instruction_phrase: _citation_for(rule.instruction_phrase, instructions)
                        for rule in self._rules[I765] if rule.instruction_phrase}

    @property
    def supported_forms(self) -> tuple[FormId, ...]:
        return tuple(self._rules)

    def review(self, form: FilledForm) -> list[Issue]:
        rules = self._rules.get(form.form)
        if rules is None:
            supported = ", ".join(str(form_id) for form_id in self._rules)
            raise UnreadableFormError(f"ClearPath can check Form {supported} for now, not Form {form.form}.")
        issues = [Issue(severity, rule.location, message, self._labels.get(rule.instruction_phrase))
                  for rule in rules for severity, message in rule.check(form)]
        return sorted(issues, key=lambda issue: issue.severity is not Severity.ERROR)  # errors first, stable order


def _citation_for(phrase: str, instructions: list[Chunk]) -> str:
    for chunk in instructions:
        if chunk.contains(phrase):
            return Citation.of(chunk).label
    raise ValueError(f"No instruction passage contains the review phrase {phrase!r}")


__all__ = ["FormReviewer", "I765", "Rule"]
