from datetime import date

import pytest

from immigration_helper.ingestion.chunk_store import ChunkStore
from immigration_helper.models import Chunk, FormId


def test_chunks_round_trip(tmp_path):
    chunk = Chunk(
        id="I-765-0001",
        form=FormId("I-765"),
        edition=date(2025, 8, 21),
        document_title="Form I-765 Instructions",
        heading_path=("Specific Instructions", "Part 2. Information About You"),
        text="Provide your A-Number.",
        page_start=18,
        page_end=19,
    )
    store = ChunkStore(tmp_path / "index" / "chunks.jsonl")

    store.save([chunk])

    assert store.load() == [chunk]


def test_form_id_rejects_non_uscis_numbers():
    with pytest.raises(ValueError):
        FormId("765")
