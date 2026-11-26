"""Domain types shared across ingestion and retrieval."""
import re
from dataclasses import dataclass
from datetime import date

_FORM_ID_PATTERN = re.compile(r"^I-\d{3}[A-Z]?$")


@dataclass(frozen=True)
class FormId:
    """A USCIS form number such as ``I-765``."""

    value: str

    def __post_init__(self) -> None:
        if not _FORM_ID_PATTERN.match(self.value):
            raise ValueError(f"Not a USCIS form number: {self.value!r}")

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True)
class Chunk:
    """A retrievable passage of a form's instructions, with where it came from."""

    id: str
    form: FormId
    edition: date
    document_title: str
    heading_path: tuple[str, ...]
    text: str
    page_start: int
    page_end: int

    @property
    def context_header(self) -> str:
        """Where the passage sits in the document, e.g. ``... > Part 2. Information About You``."""
        return " > ".join((self.document_title, *self.heading_path))

    def search_text(self) -> str:
        """Text to index for search: the header gives otherwise ambiguous passages their meaning."""
        return f"{self.context_header}\n\n{self.text}"

    def word_count(self) -> int:
        return len(self.text.split())

    def contains(self, phrase: str) -> bool:
        """Whether the passage contains the phrase, ignoring case and line breaks (labels copied from the PDFs)."""
        return _normalize(phrase) in _normalize(self.text)


def _normalize(text: str) -> str:
    return " ".join(text.lower().split())
