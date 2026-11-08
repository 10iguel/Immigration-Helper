from datetime import date

from immigration_helper.models import Chunk, FormId


def make_chunk(text: str, form: str = "I-765", chunk_id: str | None = None, heading: str = "") -> Chunk:
    return Chunk(
        id=chunk_id or f"{form}-0001",
        form=FormId(form),
        edition=date(2025, 8, 21),
        document_title=f"Form {form} Instructions",
        heading_path=(heading,) if heading else (),
        text=text,
        page_start=1,
        page_end=1,
    )
