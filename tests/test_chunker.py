from datetime import date
from pathlib import Path

from immigration_helper.ingestion.blocks import BlockKind, InstructionDocument, TextBlock
from immigration_helper.ingestion.chunker import SectionChunker
from immigration_helper.models import FormId


def make_document(*blocks: TextBlock) -> InstructionDocument:
    return InstructionDocument(
        form=FormId("I-765"),
        edition=date(2025, 8, 21),
        title="Form I-765 Instructions",
        source=Path("i-765instr.pdf"),
        blocks=blocks,
    )


def section(text: str) -> TextBlock:
    return TextBlock(BlockKind.SECTION, text, page=1)


def subsection(text: str) -> TextBlock:
    return TextBlock(BlockKind.SUBSECTION, text, page=1)


def body(text: str, lead: str = "", page: int = 1) -> TextBlock:
    return TextBlock(BlockKind.BODY, text, page, lead)


def test_each_item_number_starts_its_own_chunk():
    document = make_document(
        section("Specific Instructions"),
        subsection("Part 2. Information About You"),
        body("Item Number 8. Alien Registration Number (A-Number). Provide your A-Number.",
             lead="Item Number 8. Alien Registration Number (A-Number)."),
        body("Item Number 10. Sex. Indicate whether you are male or female.", lead="Item Number 10. Sex."),
    )

    chunks = SectionChunker().chunk(document)

    assert [chunk.heading_path[-1] for chunk in chunks] == [
        "Item Number 8. Alien Registration Number (A-Number).",
        "Item Number 10. Sex.",
    ]
    assert chunks[0].context_header == (
        "Form I-765 Instructions > Specific Instructions > Part 2. Information About You"
        " > Item Number 8. Alien Registration Number (A-Number)."
    )


def test_lettered_entries_nest_under_their_numbered_entry():
    document = make_document(
        section("Who May File Form I-765?"),
        body("3. Temporary Protected Status (TPS)--(a)(12) and (c)(19). File with Form I-821.",
             lead="3. Temporary Protected Status (TPS)--(a)(12) and (c)(19)."),
        body("A. Category (a)(12) EAD: If we granted you TPS...", lead="A. Category (a)(12) EAD:"),
        body("4. Applicant for Cancellation of Removal--(c)(10). File with...",
             lead="4. Applicant for Cancellation of Removal--(c)(10)."),
    )

    paths = [chunk.heading_path for chunk in SectionChunker().chunk(document)]

    assert paths == [
        ("Who May File Form I-765?", "3. Temporary Protected Status (TPS)--(a)(12) and (c)(19)."),
        ("Who May File Form I-765?", "3. Temporary Protected Status (TPS)--(a)(12) and (c)(19).",
         "A. Category (a)(12) EAD:"),
        ("Who May File Form I-765?", "4. Applicant for Cancellation of Removal--(c)(10)."),
    ]


def test_new_subsection_clears_enclosing_entries():
    document = make_document(
        section("Who May File Form I-765?"),
        body("1. Citizen of Micronesia--(a)(8). File with evidence.", lead="1. Citizen of Micronesia--(a)(8)."),
        subsection("Foreign Students Categories"),
        body("Students may apply for OPT."),
    )

    chunks = SectionChunker().chunk(document)

    assert chunks[-1].heading_path == ("Who May File Form I-765?", "Foreign Students Categories")


def test_short_numbered_sentence_is_not_an_entry():
    document = make_document(
        section("Who May File Form I-765?"),
        body("Your Form I-765 will be decided within 60 days if:"),
        body("1. You identify yourself as an ABC class member.", lead="1."),
    )

    chunks = SectionChunker().chunk(document)

    assert len(chunks) == 1


def test_paragraphs_are_packed_until_word_limit():
    document = make_document(
        section("General Instructions"),
        body("one two three", page=1),
        body("four five six", page=2),
        body("seven eight nine", page=3),
    )

    chunks = SectionChunker(max_words=6).chunk(document)

    assert [chunk.text for chunk in chunks] == ["one two three four five six", "seven eight nine"]
    assert (chunks[0].page_start, chunks[0].page_end) == (1, 2)


def test_long_paragraph_is_split_at_sentences():
    document = make_document(
        section("Penalties"),
        body("First sentence here. Second sentence here. Third sentence here."),
    )

    chunks = SectionChunker(max_words=6).chunk(document)

    assert [chunk.text for chunk in chunks] == ["First sentence here. Second sentence here.", "Third sentence here."]


def test_label_only_entry_is_skipped():
    document = make_document(
        section("Who May File Form I-765?"),
        body("C. Basis for Work Authorization.", lead="C. Basis for Work Authorization."),
        body("(1) Evidence of status. Submit a copy.", lead="(1) Evidence of status."),
    )

    chunks = SectionChunker().chunk(document)

    assert len(chunks) == 1
    assert chunks[0].heading_path[-2:] == ("C. Basis for Work Authorization.", "(1) Evidence of status.")


def test_a_notes_header_starts_its_own_chunk_holding_the_notes():
    document = make_document(
        section("Who May File Form I-130"),
        body("2. If you are a lawful permanent resident, you may file for: A. Your spouse.", lead="2."),
        body("NOTE:", lead="NOTE:"),
        body("1. If you are filing for your spouse, he or she must complete and sign Form I-130A.", lead="1."),
        body("2. There is no visa category for married children of lawful permanent residents.", lead="2."),
        section("Who May Not File Form I-130?"),
        body("NOTE: Do not file for a grandparent.", lead="NOTE:"),
    )

    chunks = SectionChunker().chunk(document)

    assert [chunk.heading_path for chunk in chunks] == [
        ("Who May File Form I-130",),
        ("Who May File Form I-130", "Notes"),
        ("Who May Not File Form I-130?",),  # a note inside a paragraph stays with its section
    ]
    assert chunks[1].text.startswith("NOTE: 1. If you are filing for your spouse")
    assert "married children" in chunks[1].text
