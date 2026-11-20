"""What the assistant returns: an answer and the sources it is based on."""
from dataclasses import dataclass
from enum import Enum

from immigration_helper.chat_model import ChatUsage
from immigration_helper.models import Chunk, FormId


@dataclass(frozen=True)
class Citation:
    """A source built from the chunk's stored metadata, never from model output."""

    chunk_id: str
    form: FormId
    label: str

    @classmethod
    def of(cls, chunk: Chunk) -> "Citation":
        pages = f"p. {chunk.page_start}" if chunk.page_start == chunk.page_end else f"pp. {chunk.page_start}-{chunk.page_end}"
        section = " > ".join(chunk.heading_path)
        return cls(chunk.id, chunk.form, f"Form {chunk.form} Instructions ({chunk.edition:%m/%d/%y}), {pages}: {section}")


class ReplyKind(Enum):
    ANSWER = "answer"  # searched, and the passages answer the question
    NOT_COVERED = "not_covered"  # searched, and the loaded instructions don't answer it
    CONVERSATION = "conversation"  # small talk (thanks, hello, what can you do?): no search, no facts


@dataclass(frozen=True)
class Answer:
    question: str
    kind: ReplyKind
    text: str
    citations: tuple[Citation, ...]
    rejected_citation_ids: tuple[str, ...]  # IDs the model cited that were not among its passages
    usage: ChatUsage
    passages: tuple[Chunk, ...]  # what the model was shown, so the answer can be checked against it
    searches: tuple[str, ...] = ()  # the search queries the model wrote, in order
    withheld_text: str | None = None  # an answer without a valid source, replaced before anyone saw it

    @property
    def answerable(self) -> bool:
        return self.kind is ReplyKind.ANSWER

    @property
    def is_grounded(self) -> bool:
        """True when an answer cites at least one passage it was given and nothing else."""
        return self.answerable and bool(self.citations) and not self.rejected_citation_ids
