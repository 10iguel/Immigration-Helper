"""A filled-in USCIS form, read from its fillable PDF fields, and the problems found in it."""
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import date, datetime
from enum import Enum

from immigration_helper.models import FormId

UNCHECKED = "Off"  # the value PDF checkboxes have when they're not selected


@dataclass(frozen=True)
class FilledForm:
    """Field values keyed by page and field name, e.g. "Page2[0].Line7_AlienNumber[0]".

    The values are personal data: they live only in memory while the form is checked, and are never stored or logged.
    """
    form: FormId
    edition: date | None  # the edition printed in the form's footer
    values: Mapping[str, str] = field(repr=False)

    def text(self, name: str) -> str:
        return self.values.get(name, "").strip()

    def selected(self, names: tuple[str, ...]) -> list[str]:
        """The checkboxes among ``names`` that are selected."""
        return [name for name in names if self.values.get(name, UNCHECKED) not in (UNCHECKED, "")]


class Severity(Enum):
    ERROR = "error"  # USCIS could reject the form or delay the case
    WARNING = "warning"  # worth checking before mailing


@dataclass(frozen=True)
class Issue:
    """A problem found in a form. It names a place on the form, never the value the person entered."""
    severity: Severity
    location: str  # e.g. "Part 2, Item Number 16"
    message: str
    instruction_label: str | None = None  # the instruction passage behind the check, as a citation label


def parse_form_date(text: str) -> date | None:
    """A date written the way USCIS forms ask for it (mm/dd/yyyy), or None."""
    try:
        return datetime.strptime(text, "%m/%d/%Y").date()
    except ValueError:
        return None
