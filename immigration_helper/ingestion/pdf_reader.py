"""Reads USCIS instruction PDFs into classified text blocks using their font layout."""
import re
from collections import Counter
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

import pymupdf

from immigration_helper.ingestion.blocks import BlockKind, InstructionDocument, TextBlock, list_entry_level
from immigration_helper.models import FormId

# Every page header reads like "Form I-765 Instructions   08/21/25".
_PAGE_HEADER_PATTERN = re.compile(r"Form (I-\d{3}[A-Z]?) Instructions\s+(\d{2}/\d{2}/\d{2})")
_WORD_PATTERN = re.compile(r"[A-Za-z][\w'/-]*")
_BOLD_FLAG = 16
_MIN_HEADING_BOLD_RATIO = 0.95
_MAX_SUBSECTION_LENGTH = 160
_MIN_TITLE_CASE_RATIO = 0.6


@dataclass(frozen=True)
class _RawBlock:
    page: int
    font_size: float
    bold_ratio: float
    text: str
    lead: str


class InstructionReader:
    """Turns an instructions PDF into an ``InstructionDocument``.

    Layout rules (consistent across USCIS instructions):
    - text smaller than the body font is page header/footer fine print;
    - the most common bold size above the body font marks sections; larger bold text is the title;
    - a short, fully bold, Title Case line at body size is a subsection (e.g. "Part 2.  Information
      About You"), unless it is a numbered list entry, which the chunker treats as a labeled item;
    - everything before the first section is the cover page and table of contents.
    """

    def read(self, path: Path) -> InstructionDocument:
        with pymupdf.open(path) as pdf:
            title = pdf.metadata.get("title") or ""
            raw_blocks = [block for page in pdf for block in self._read_page(page)]
        form, edition = self._identify(raw_blocks, path)
        blocks = self._classify(raw_blocks)
        return InstructionDocument(
            form=form,
            edition=edition,
            title=title or f"Form {form} Instructions",
            source=path,
            blocks=tuple(blocks),
        )

    def _read_page(self, page: pymupdf.Page) -> list[_RawBlock]:
        blocks = []
        for block in page.get_text("dict", sort=True)["blocks"]:
            all_spans = [span for line in block.get("lines", []) for span in line["spans"]]
            spans = [span for span in all_spans if span["text"].strip()]
            if not spans:
                continue
            blocks.append(_RawBlock(
                page=page.number + 1,
                font_size=self._dominant_size(spans),
                bold_ratio=self._bold_ratio(spans),
                text=self._join_lines(block["lines"]),
                lead=self._bold_lead(all_spans),
            ))
        return blocks

    def _identify(self, raw_blocks: list[_RawBlock], path: Path) -> tuple[FormId, date]:
        for block in raw_blocks:
            match = _PAGE_HEADER_PATTERN.search(block.text)
            if match:
                edition = datetime.strptime(match.group(2), "%m/%d/%y").date()
                return FormId(match.group(1)), edition
        raise ValueError(f"No 'Form I-XXX Instructions mm/dd/yy' page header found in {path}")

    def _classify(self, raw_blocks: list[_RawBlock]) -> list[TextBlock]:
        body_size = self._most_common_size(raw_blocks)
        section_size = self._most_common_size(
            [b for b in raw_blocks if b.font_size > body_size and b.bold_ratio >= _MIN_HEADING_BOLD_RATIO]
        )
        blocks: list[TextBlock] = []
        for raw in raw_blocks:
            if raw.font_size < body_size:
                continue
            if raw.font_size > body_size:
                if raw.font_size == section_size and raw.bold_ratio >= _MIN_HEADING_BOLD_RATIO:
                    blocks.append(TextBlock(BlockKind.SECTION, raw.text, raw.page))
                continue
            if not blocks:
                continue  # cover page and table of contents
            kind = BlockKind.SUBSECTION if self._is_subsection(raw) else BlockKind.BODY
            blocks.append(TextBlock(kind, raw.text, raw.page, raw.lead))
        return blocks

    @staticmethod
    def _is_subsection(raw: _RawBlock) -> bool:
        return (
            raw.bold_ratio >= _MIN_HEADING_BOLD_RATIO
            and len(raw.text) <= _MAX_SUBSECTION_LENGTH
            and not raw.text.startswith("NOTE")
            and list_entry_level(raw.text) is None
            and InstructionReader._is_title_case(raw.text)
        )

    @staticmethod
    def _is_title_case(text: str) -> bool:
        # Filters out bold sentences ("We recommend that you print...") that are not headings.
        words = [word for word in _WORD_PATTERN.findall(text) if len(word) > 3]
        if not words:
            return False
        capitalized = sum(word[0].isupper() for word in words)
        return capitalized / len(words) >= _MIN_TITLE_CASE_RATIO

    @staticmethod
    def _most_common_size(blocks: list[_RawBlock]) -> float:
        if not blocks:
            raise ValueError("Cannot determine font sizes: no text blocks")
        sizes = Counter()
        for block in blocks:
            sizes[block.font_size] += len(block.text)
        return sizes.most_common(1)[0][0]

    @staticmethod
    def _dominant_size(spans: list[dict]) -> float:
        sizes = Counter()
        for span in spans:
            sizes[round(span["size"])] += len(span["text"])
        return sizes.most_common(1)[0][0]

    @staticmethod
    def _bold_ratio(spans: list[dict]) -> float:
        total = sum(len(span["text"]) for span in spans)
        bold = sum(len(span["text"]) for span in spans if span["flags"] & _BOLD_FLAG)
        return bold / total

    @staticmethod
    def _bold_lead(spans: list[dict]) -> str:
        # Non-bold spaces and dashes inside a label ("Item Numbers 7.a. - 7.e.") don't end it.
        lead = []
        for span in spans:
            if not span["flags"] & _BOLD_FLAG and any(char.isalnum() for char in span["text"]):
                break
            lead.append(span["text"])
        return _normalize("".join(lead).rstrip(" -"))

    @staticmethod
    def _join_lines(lines: list[dict]) -> str:
        text = ""
        for line in lines:
            line_text = "".join(span["text"] for span in line["spans"]).strip()
            # "Form I-" + "130" or "self-" + "petition": a trailing hyphen continues the word.
            separator = "" if text.endswith("-") else " "
            text = f"{text}{separator}{line_text}" if text else line_text
        return _normalize(text)


def _normalize(text: str) -> str:
    text = text.replace("\x08", " ").replace("’", "'").replace("“", '"').replace("”", '"')
    return re.sub(r"\s+", " ", text).strip()
