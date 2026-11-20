"""Keeps the uscis_form lookup table in step with the ingested instructions."""
from collections.abc import Iterable

from immigration_helper.models import Chunk
from immigration_helper.storage.database import Database


def sync_forms(database: Database, chunks: Iterable[Chunk]) -> int:
    """Adds or updates one row per form found in the chunks, so every citation's form_id exists. Returns the count."""
    forms = {chunk.form.value: (chunk.document_title, chunk.edition) for chunk in chunks}
    with database.connect() as connection, connection.cursor() as cursor:
        cursor.executemany(
            "INSERT INTO uscis_form (form_id, title, edition_date) VALUES (%s, %s, %s) "
            "ON CONFLICT (form_id) DO UPDATE SET title = EXCLUDED.title, edition_date = EXCLUDED.edition_date",
            [(form_id, title, edition) for form_id, (title, edition) in forms.items()],
        )
    return len(forms)
