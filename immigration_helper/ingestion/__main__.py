"""Ingest all instruction PDFs: python -m immigration_helper.ingestion"""
import argparse
from pathlib import Path

from immigration_helper import config
from immigration_helper.ingestion import ChunkStore, InstructionReader, SectionChunker
from immigration_helper.models import Chunk


def main() -> None:
    parser = argparse.ArgumentParser(description="Chunk USCIS instruction PDFs.")
    parser.add_argument("--forms-dir", type=Path, default=config.FORMS_DIR)
    parser.add_argument("--output", type=Path, default=config.CHUNKS_PATH)
    parser.add_argument("--max-words", type=int, default=300)
    args = parser.parse_args()

    paths = sorted(args.forms_dir.glob("*instr.pdf"))
    if not paths:
        raise SystemExit(f"No *instr.pdf files in {args.forms_dir}")

    reader, chunker = InstructionReader(), SectionChunker(args.max_words)
    chunks: list[Chunk] = []
    for path in paths:
        document = reader.read(path)
        document_chunks = chunker.chunk(document)
        print_summary(document.form, document.edition, document_chunks)
        chunks.extend(document_chunks)

    ChunkStore(args.output).save(chunks)
    print(f"\nSaved {len(chunks)} chunks to {args.output}")


def print_summary(form, edition, chunks: list[Chunk]) -> None:
    words = [chunk.word_count() for chunk in chunks]
    print(f"Form {form} (edition {edition:%m/%d/%Y}): {len(chunks)} chunks, "
          f"words min {min(words)} / avg {sum(words) // len(words)} / max {max(words)}")


if __name__ == "__main__":
    main()
