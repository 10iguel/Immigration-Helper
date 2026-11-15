"""What the assistant returns: an answer and the sources it is based on."""
from dataclasses import dataclass

from immigration_helper.chat_model import ChatUsage
from immigration_helper.models import Chunk


@dataclass(frozen=True)
class Citation:
    """A source built from the chunk's stored metadata, never from model output."""

    chunk_id: str
    label: str

    @classmethod
    def of(cls, chunk: Chunk) -> "Citation":
        pages = f"p. {chunk.page_start}" if chunk.page_start == chunk.page_end else f"pp. {chunk.page_start}-{chunk.page_end}"
        section = " > ".join(chunk.heading_path)
        return cls(chunk.id, f"Form {chunk.form} Instructions ({chunk.edition:%m/%d/%y}), {pages}: {section}")


@dataclass(frozen=True)
class Answer:
    question: str
    answerable: bool
    text: str
    citations: tuple[Citation, ...]
    rejected_citation_ids: tuple[str, ...]  # IDs the model cited that were not among its passages
    usage: ChatUsage
    passages: tuple[Chunk, ...]  # what the model was shown, so the answer can be checked against it

    @property
    def is_grounded(self) -> bool:
        """True when an answer cites at least one passage it was given and nothing else."""
        return self.answerable and bool(self.citations) and not self.rejected_citation_ids
