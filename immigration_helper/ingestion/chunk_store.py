"""Saves and loads chunks as JSON Lines, one chunk per line."""
import json
from datetime import date
from pathlib import Path

from immigration_helper.models import Chunk, FormId


class ChunkStore:
    def __init__(self, path: Path):
        self._path = path

    def save(self, chunks: list[Chunk]) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with self._path.open("w", encoding="utf-8") as file:
            for chunk in chunks:
                file.write(json.dumps(self._to_record(chunk), ensure_ascii=False) + "\n")

    def load(self) -> list[Chunk]:
        with self._path.open(encoding="utf-8") as file:
            return [self._from_record(json.loads(line)) for line in file if line.strip()]

    @staticmethod
    def _to_record(chunk: Chunk) -> dict:
        return {
            "id": chunk.id,
            "form": str(chunk.form),
            "edition": chunk.edition.isoformat(),
            "document_title": chunk.document_title,
            "heading_path": list(chunk.heading_path),
            "text": chunk.text,
            "page_start": chunk.page_start,
            "page_end": chunk.page_end,
        }

    @staticmethod
    def _from_record(record: dict) -> Chunk:
        return Chunk(
            id=record["id"],
            form=FormId(record["form"]),
            edition=date.fromisoformat(record["edition"]),
            document_title=record["document_title"],
            heading_path=tuple(record["heading_path"]),
            text=record["text"],
            page_start=record["page_start"],
            page_end=record["page_end"],
        )
