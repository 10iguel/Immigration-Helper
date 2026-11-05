"""Intermediate representation between PDF reading and chunking."""
import re
from dataclasses import dataclass
from datetime import date
from enum import Enum, auto
from pathlib import Path

from immigration_helper.models import FormId

# List entry markers from outermost to innermost: "Item Number 8." / "3.", then "A.", then "(3)".
_LIST_ENTRY_LEVELS = (
    re.compile(r"^(Item Numbers? |\d+\.\s)"),
    re.compile(r"^[A-Z]\.\s"),
    re.compile(r"^\(\d+\)\s"),
)


def list_entry_level(text: str) -> int | None:
    """Nesting depth (0 = outermost) of a list entry such as an eligibility category, else None."""
    for level, pattern in enumerate(_LIST_ENTRY_LEVELS):
        if pattern.match(text):
            return level
    return None


class BlockKind(Enum):
    SECTION = auto()
    SUBSECTION = auto()
    BODY = auto()


@dataclass(frozen=True)
class TextBlock:
    """One paragraph or heading of the instructions."""

    kind: BlockKind
    text: str
    page: int
    lead: str = ""  # bold lead-in, e.g. "Item Number 8.  Alien Registration Number (A-Number) (if any)."


@dataclass(frozen=True)
class InstructionDocument:
    """A form's instructions as an ordered list of classified blocks."""

    form: FormId
    edition: date
    title: str
    source: Path
    blocks: tuple[TextBlock, ...]
