# Immigration Helper (USCIS Form Helper)

> **Disclaimer:** This project is a class project, not legal advice. Always confirm answers
> against the official instructions on [uscis.gov](https://www.uscis.gov) or with an immigration attorney.

## Problem

USCIS paperwork is repetitive and the guidance is scattered across long PDF instructions full of
specialized jargon ("EAD", "adjustment of status", "eligibility category (c)(9)", "A-Number").
Applicants re-type the same information on every form and struggle to find the answer to
form-specific questions, which leads to costly mistakes.

## What it does

1. **Form Q&A (core concept: Embeddings / RAG)** — answers questions about a form using only the
   official USCIS instructions, and cites the form, Part and edition date the answer came from.
   If the retrieved text doesn't support an answer, it says so instead of guessing.
2. **Document vault** — keeps the user's recurring documents (passport, I-94, green card,
   receipt notices) locally so the same data can be reused across forms.

## Retrieval design

USCIS instructions use jargon and exact codes that plain embedding search handles poorly, so
retrieval is built in layers, and each layer is measured against a test set of questions:

| Layer | Handles |
|---|---|
| Section-aware chunking with a context header (`Form I-765 > Part 2 > Item 27`) on every chunk | Chunks that make no sense out of context |
| LLM query rewriting using the USCIS glossary ("work permit" → "Employment Authorization Document, Form I-765") | Plain-language questions vs. official terms |
| Hybrid search: dense embeddings + BM25 keyword search, merged with reciprocal rank fusion | Exact codes and form numbers (`I-765`, `(c)(8)`) |
| Reranking the top candidates with a cross-encoder | Picking the best passage among close matches |

**Evaluation:** [`data/eval/eval_set.json`](data/eval/eval_set.json) has 31 answer targets across the four
forms. Each is asked twice, once in plain words ("Can I get permission to work while I wait?") and once in
USCIS jargon ("How do I file Form I-765 under category (c)(9)?"), so comparing the pair shows how much the
vocabulary gap hurts retrieval. The targets include harder cases on purpose: deadlines and numbers (t19, t25,
t26), negative questions such as "who may *not* file" (t27–t29), passages repeated in two places (t30), and
category-specific exceptions that override a general rule (t31 vs. t20). Five more questions aren't answered by
any loaded instructions (o01–o05; o04 and o05 are close to the topic, about fees and processing times) and test
whether the app admits it doesn't know.

Answers are labeled with phrases copied from the official text, not chunk IDs, so the same labels work for any
chunking strategy: a chunk is relevant if it comes from the right form and contains one of the phrases.
Retrieval will be scored by Recall@5 and MRR, compared against a keyword-only baseline. To check that every
target still matches a chunk after changing the chunker:

```bash
.venv/Scripts/python -m immigration_helper.evaluation
```

## Planned stack

- Python, `pymupdf` for PDF parsing
- OpenAI for both embeddings (`text-embedding-3-small`, compared against `-large`) and answer generation
- Vector store: Chroma (local)
- Keyword search: `rank_bm25`
- The API key is read from `OPENAI_API_KEY` in a git-ignored `.env` file

## Getting started

```bash
python -m venv .venv
.venv/Scripts/pip install -r requirements.txt   # macOS/Linux: .venv/bin/pip
.venv/Scripts/python -m immigration_helper.ingestion   # chunks data/forms/*instr.pdf -> data/index/chunks.jsonl
.venv/Scripts/python -m pytest
```

## Ingestion and chunking

`InstructionReader` uses the PDFs' consistent font layout to classify each paragraph: 12pt bold is a
section, a short fully bold Title Case line is a subsection ("Part 2.  Information About You"), 9pt text is the
page header (where the edition date is read from), and everything before the first section is the cover and
table of contents.

`SectionChunker` then starts a new chunk at every heading and every labeled list entry ("Item Number 8.",
an eligibility category like "3. Temporary Protected Status--(a)(12) and (c)(19).", and nested "A." / "(1)"
sub-entries). Every chunk keeps its full heading path, which is prepended before embedding, e.g.:

```
Form I-765, Instructions for Application for Employment Authorization > Who May File Form I-765?
> Adjustment of Status Categories > 1. Adjustment Applicant under Section 245--(c)(9).
```

Known limitation: when a PDF resumes a numbered list after a subsection without a new heading, the following
entries inherit that subsection in their path.

## Repository layout

```
immigration_helper/
  models.py     FormId, Chunk
  ingestion/    PDF reading, chunking, chunk storage
tests/
data/
  forms/      official USCIS PDFs (see data/README.md)
  personal/   user's own documents (git-ignored)
  index/      generated chunks and vector store (git-ignored)
```

## Milestones

- [ ] Download form instructions and record edition dates
- [ ] Ingestion: parse PDFs, chunk by section, embed into Chroma
- [ ] Basic Q&A with citations
- [ ] Test set of ~30 questions + Recall@5 / MRR evaluation
- [ ] Hybrid search, query rewriting, reranking (measure each)
- [ ] Document vault
- [ ] Cost measurements, screenshots, report and slides
