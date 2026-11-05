"""Splits an instruction document into chunks that follow its own structure."""
import re
from dataclasses import dataclass, field

from immigration_helper.ingestion.blocks import BlockKind, InstructionDocument, TextBlock, list_entry_level
from immigration_helper.models import Chunk

_MIN_LABEL_WORDS = 3  # "1." alone is a plain numbered sentence, not a labeled entry
_SENTENCE_END = re.compile(r"(?<=[.;:])\s+")


@dataclass
class _Draft:
    heading_path: tuple[str, ...]
    blocks: list[TextBlock] = field(default_factory=list)

    def word_count(self) -> int:
        return sum(len(block.text.split()) for block in self.blocks)


class SectionChunker:
    """Chunks by section > subsection > list entries, so each chunk answers one kind of question.

    A new chunk starts at every heading and every labeled list entry: an "Item Number" paragraph or
    a numbered entry such as an eligibility category, with lettered sub-entries nested under it.
    Within a heading, paragraphs are packed together until ``max_words``; a single paragraph longer
    than that is split at sentence boundaries.
    """

    def __init__(self, max_words: int = 300):
        self._max_words = max_words

    def chunk(self, document: InstructionDocument) -> list[Chunk]:
        drafts: list[_Draft] = []
        headings: list[str] = []  # [section, subsection?]
        entries: list[str | None] = []  # enclosing list entry label per nesting level, outermost first
        current = _Draft(heading_path=())

        for block in document.blocks:
            level = self._entry_level(block)
            if block.kind is BlockKind.SECTION:
                headings, entries = [block.text], []
            elif block.kind is BlockKind.SUBSECTION:
                headings, entries = headings[:1] + [block.text], []
            elif level is not None:
                entries = (entries + [None] * level)[:level] + [block.lead]
            elif not current.blocks or current.word_count() + len(block.text.split()) <= self._max_words:
                current.blocks.append(block)
                continue

            if current.blocks:
                drafts.append(current)
            current = _Draft(heading_path=tuple(headings + [entry for entry in entries if entry]))
            if block.kind is BlockKind.BODY:
                current.blocks.append(block)

        if current.blocks:
            drafts.append(current)
        return self._to_chunks(document, drafts)

    @staticmethod
    def _entry_level(block: TextBlock) -> int | None:
        if block.kind is not BlockKind.BODY or len(block.lead.split()) < _MIN_LABEL_WORDS:
            return None
        return list_entry_level(block.lead)

    def _to_chunks(self, document: InstructionDocument, drafts: list[_Draft]) -> list[Chunk]:
        chunks = []
        for draft in drafts:
            if self._is_label_only(draft):
                continue  # e.g. "C. Basis for Work Authorization." whose content is in its sub-entries
            text = " ".join(block.text for block in draft.blocks)
            for piece in self._split_long(text):
                chunks.append(Chunk(
                    id=f"{document.form}-{len(chunks):04d}",
                    form=document.form,
                    edition=document.edition,
                    document_title=document.title,
                    heading_path=draft.heading_path,
                    text=piece,
                    page_start=draft.blocks[0].page,
                    page_end=draft.blocks[-1].page,
                ))
        return chunks

    @staticmethod
    def _is_label_only(draft: _Draft) -> bool:
        return len(draft.blocks) == 1 and draft.blocks[0].text == draft.blocks[0].lead

    def _split_long(self, text: str) -> list[str]:
        if len(text.split()) <= self._max_words:
            return [text]
        pieces, current = [], []
        for sentence in _SENTENCE_END.split(text):
            if current and len(" ".join(current + [sentence]).split()) > self._max_words:
                pieces.append(" ".join(current))
                current = []
            current.append(sentence)
        if current:
            pieces.append(" ".join(current))
        return pieces
