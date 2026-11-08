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
Retrieval is scored by Recall@1, Recall@5 and MRR (mean reciprocal rank of the first relevant chunk in the top
10), overall and per question style.

```bash
# check that every target still matches a chunk (run after changing the chunker or the eval set)
.venv/Scripts/python -m immigration_helper.evaluation validate
# score keyword and embedding search; prints a table and saves results/retrieval-<timestamp>.json
.venv/Scripts/python -m immigration_helper.evaluation retrieval
# keyword search only (free, no API calls)
.venv/Scripts/python -m immigration_helper.evaluation retrieval --retrievers keyword
```

The embedding index is stored in `data/index/chroma` and rebuilt only when the chunks or the embedding model
change, so after the first run only the questions are embedded.

## Planned stack

- Python, `pymupdf` for PDF parsing
- OpenAI for both embeddings (`text-embedding-3-small`, compared against `-large`) and answer generation
- Vector store: Chroma (local)
- Keyword search: `rank_bm25`
- The API key is read from the `OPENAI_API_KEY` environment variable

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

## Retrieval results

Baseline run on 2026-11-07 (62 answerable questions, 465 chunks; [`results/retrieval-20261107-191343.json`](results/retrieval-20261107-191343.json)):

| Retriever | Style | Recall@1 | Recall@5 | MRR |
|---|---|---|---|---|
| Keyword (BM25) | plain | 0.26 | 0.42 | 0.34 |
| Keyword (BM25) | jargon | 0.81 | 0.90 | 0.85 |
| Keyword (BM25) | all | 0.53 | 0.66 | 0.59 |
| Embeddings (`text-embedding-3-small`) | plain | 0.52 | 0.74 | 0.60 |
| Embeddings (`text-embedding-3-small`) | jargon | 0.90 | 0.97 | 0.94 |
| Embeddings (`text-embedding-3-small`) | all | 0.71 | 0.85 | 0.77 |

- Embeddings beat keyword search in every row, most of all on plain questions (Recall@5 0.42 → 0.74).
- The vocabulary gap remains: plain questions still trail jargon ones by 23 points of Recall@5.
- 7 of the 9 embedding misses are plain questions that say "green card". The instructions say "lawful permanent
  resident" or "adjustment of status" instead: "green card" appears in only 4 of the 465 chunks, and "work permit"
  in none. This motivates glossary-based query rewriting as the next layer.
- One jargon miss (t24) found the identical "Translations" rule in the I-765 and I-131 instructions before the
  I-485 one. The answer would be right but cite the wrong form, which suggests filtering by form when the
  question names one.

Cost: building the index embedded 96,653 tokens ($0.0019, one-time). Afterwards a full run of 62 questions used
1,224 tokens ($0.000024), about 20 tokens and $0.0000004 per question.

## Repository layout

```
immigration_helper/
  models.py     FormId, Chunk
  ingestion/    PDF reading, chunking, chunk storage
  retrieval/    Retriever interface, keyword (BM25) and embedding (OpenAI + Chroma) search
  evaluation/   evaluation set, retrieval metrics, evaluation commands
results/        saved evaluation runs (JSON)
tests/
data/
  forms/      official USCIS PDFs (see data/README.md)
  personal/   user's own documents (git-ignored)
  index/      generated chunks and vector store (git-ignored)
```

## Milestones

- [x] Download form instructions and record edition dates
- [x] Ingestion: parse PDFs, chunk by section, embed into Chroma
- [ ] Basic Q&A with citations
- [x] Evaluation set (31 targets × plain/jargon + 5 out of scope) and Recall@k / MRR evaluation
- [x] Baseline retrieval: keyword (BM25) vs. embeddings
- [ ] Hybrid search, query rewriting, reranking (measure each)
- [ ] Document vault
- [ ] Cost measurements, screenshots, report and slides
