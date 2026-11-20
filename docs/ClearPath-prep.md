# ClearPath for Immigration: Pitch and Interview Prep

> **How to use this page:** read one part at a time. Each part starts with a 30-second version.
> Everything here is true about your project as of 2026-11-19.

**Contents**
1. [Teams post](#1-teams-post-copy-and-paste)
2. [The 1-minute spoken pitch](#2-the-1-minute-spoken-pitch)
3. [Numbers to remember](#3-numbers-to-remember)
4. [Data modeling interview](#4-live-data-modeling-interview)
5. [System design interview](#5-system-design-interview-your-project)
6. [Day-of checklist](#6-day-of-checklist)

---

## 1. Teams post (copy and paste)

**ClearPath for Immigration: Project Pitch**

Hi everyone! I'm building ClearPath for Immigration, an assistant that helps people with USCIS immigration forms
(I-130, I-131, I-485 and I-765). I want to work on this because immigration paperwork is stressful and confusing,
and one mistake can delay a case for months. The instructions are long and full of legal terms: people say "green
card," but the instructions say "adjustment of status." With ClearPath, users can ask questions in plain words and
get answers based only on the official instructions, with the form, page and section cited. It says "the
instructions don't cover this" instead of guessing. Users will also be able to upload their filled-out forms so
ClearPath can check them for errors or missing information before they send them to USCIS, and their chat history
will be saved so they can come back and ask follow-up questions.

I'm using Python, OpenAI embeddings stored in a Chroma vector database, GPT-4.1-mini for answers, FastAPI for the
server and Next.js for the website, plus a database for users, uploaded forms and chat history. The question
answering already works: on a test set of 82 questions, it is about 95% correct. Next, I'll add the chat history and
then the form review, and I'd love feedback on which mistakes people most often make on these forms.

> ✏️ **Optional:** if you have a personal reason (your family, friends or your own forms), add one sentence to the
> second paragraph. A personal reason makes a pitch much stronger.

---

## 2. The 1-minute spoken pitch

Say it in this order (**Problem → Solution → Proof → Ask**):

1. **Problem:** "Immigration instructions are long and full of legal words. People ask about a 'green card,' but the
   instructions say 'adjustment of status,' so normal search doesn't find the answer."
2. **Solution:** "ClearPath rewrites your question into official terms, finds the right passages, and answers in plain
   words with a citation. If the answer isn't in the instructions, it says so."
3. **Proof:** "On 82 test questions it's about 95% correct, and each answer costs about a tenth of a cent."
4. **Demo** (if you can): ask *"My birth certificate is in Spanish. Do I need to get it translated?"*
5. **Ask:** "I'd love feedback: what immigration questions would *you* want it to answer?"

---

## 3. Numbers to remember

Learn these. They make you sound like you measured everything, because you did.

| What | Number |
|---|---|
| Forms covered | 4 (I-130, I-131, I-485, I-765) |
| Chunks (searchable passages) | 466 |
| Test questions | 82 (37 plain, 37 jargon, 8 out of scope) |
| Right passage in top 5 (Recall@5) | 97% (was 74% for plain questions before query rewriting) |
| Answers correct | 95% on the tuning set, 92% on new held-out questions |
| Judge vs. me (human check) | Agreed on 13 of 15 (87%) |
| Cost per question | about $0.0013 |
| Passages sent to the model | 8 |

---

## 4. Live data modeling interview

### 30-second version
They give you a situation. You draw **boxes (entities)**, **lines (relationships)** and **keys**, and you
**talk out loud** the whole time. There's no single right answer: they want to see how you think.

### The 6-step recipe (use it every time)

| Step | Do this | Say this out loud |
|---|---|---|
| 1. Ask | Ask 2 or 3 clarifying questions | "Who uses this? What are the main things they do?" |
| 2. Nouns | Circle the nouns, which become **entities** (tables) | "I see users, documents and appointments…" |
| 3. Attributes | List a few columns per entity | "A user has a name and an email…" |
| 4. Keys | Give each table a **primary key (PK)** | "Each table gets an id as its primary key." |
| 5. Relationships | Draw lines and label **1:1, 1:N or M:N** | "One user has many documents, so the foreign key goes on documents." |
| 6. Check | Normalize, add indexes, check a query | "To find all of a user's documents, I'd index user_id." |

### Relationship cheat sheet

| Type | Example | How to build it |
|---|---|---|
| **1:N** (one-to-many) | One form has many chunks | Put the **foreign key on the "many" side**: `chunk.form_id` |
| **M:N** (many-to-many) | Messages cite many chunks, and a chunk is cited by many messages | Use a **junction table**: `citation(message_id, chunk_id)` |
| **1:1** | A chunk has one embedding | The same key in both tables, or just one table |
| **Optional** | An eval question may have no answer target | A **nullable** foreign key |
| **Lookup / enum** | Question style: plain, jargon, out of scope | A small lookup table or a CHECK constraint |

**Normalization in one sentence:** "Every fact is stored once." If you'd copy the same value into many rows
(such as a form's title in every chunk), move it to its own table.

### Practice: model YOUR project
This is very likely to come up. Here's your real data, drawn as tables.

**What exists today** (stored in JSON/JSONL files plus Chroma):

```
FORM                      CHUNK                         EMBEDDING (in Chroma)
-----------               ---------------------         ---------------------
form_id  PK  "I-485"  1──N chunk_id    PK "I-485-0009"  1──1 chunk_id  PK/FK
title                     form_id      FK               vector (1536 numbers)
edition_date              heading_path
source_pdf                text
                          page_start, page_end

ANSWER_TARGET             ANSWER_PHRASE                 EVAL_QUESTION
-------------             -------------                 -------------
target_id PK "t24"   1──N target_id FK              question_id PK "t24-plain"
form_id   FK              phrase                        target_id   FK (NULL = out of scope)
reference_answer                                        style  (plain / jargon / out_of_scope)
                                                        text
ANSWER_TARGET 1──N EVAL_QUESTION   (each target is asked twice: plain + jargon)
```

**How to explain the choices:**
- "**Chunks reference forms by `form_id`**, so the edition date is stored once, not in all 466 chunks."
- "**Answer phrases** are in their own table because one target can have several phrases (a 1:N list)."
- "**Out-of-scope questions have a NULL target**: they exist on purpose to test that the app says 'I don't know.'"
- "**Vectors live in Chroma**, not SQL, because Chroma has a fast nearest-neighbor index for 'find similar.'
  In Postgres I'd use the pgvector extension instead."
- "Relevance is labeled with **phrases, not chunk IDs**, so I can change how I chunk without relabeling the
  test set." ← this is a smart design point, so say it!

**The PostgreSQL model for users, chat history and form review** (agreed; the full SQL is in
[`db/schema.sql`](../db/schema.sql)):

```
APP_USER 1──N CONVERSATION 1──N MESSAGE 1──N CITATION N──1 USCIS_FORM
APP_USER 1──N UPLOADED_FORM 1──N FORM_ISSUE
USCIS_FORM 1──N UPLOADED_FORM
```

| Table | Key columns |
|---|---|
| `app_user` | user_id PK, email UNIQUE, password_hash |
| `conversation` | conversation_id PK, user_id FK, title, updated_at |
| `message` | message_id PK, conversation_id FK, role (user/assistant), content, answerable, cost_usd |
| `citation` | PK (message_id, position), form_id FK, chunk_id, label (a saved copy) |
| `uscis_form` | form_id PK ('I-485'), title, edition_date |
| `uploaded_form` | upload_id PK, user_id FK, form_id FK, storage_path, status |
| `form_issue` | issue_id PK, upload_id FK, severity, location ('Part 2, Item 8'), message |

**The 6 decisions, and how to say them:**
1. "Questions and answers share **one `message` table** with a `role` column, because a chat is just an ordered list
   of messages."
2. "**Citations save a copy of the label**, not a foreign key to a chunk, because chunk IDs change when I re-chunk.
   My t36 fix shifted every I-130 chunk ID by one, so old chats would have pointed to the wrong passage."
3. "Chunks and vectors **stay in Chroma**. Postgres holds only user data, plus the small `uscis_form` lookup table."
4. "Uploaded PDFs are **files on disk**, and the database stores only the path. Big files make databases slow."
5. "**ON DELETE CASCADE** from the user down, so a user can delete all their immigration data at once."
6. "**Personal values are never stored.** An issue says 'Part 2, Item 8 is empty', not the A-Number itself."

**Indexes, and why:** `message (conversation_id, created_at)` loads a chat in order; `conversation (user_id,
updated_at DESC)` lists "my chats, newest first"; `email` is UNIQUE, so it gets an index automatically.

**A CHECK constraint worth mentioning:** user messages can't have `cost_usd` or `answerable`, and the database
enforces it, so bad data can't get in even if the code has a bug.

### Questions they may ask (with short answers)
- **"Why not put everything in one table?"** It would repeat data and cause update mistakes. If a form's
  edition changes, I'd have to fix 466 rows instead of 1.
- **"SQL or NoSQL here?"** SQL for users, chats and citations, because they have clear relationships. A vector
  database for embeddings, because it's built for similarity search. Today's files are JSON because the data is
  small and read-only.
- **"What does a query look like?"** "All sources cited in a conversation":
  `SELECT DISTINCT ci.label FROM message m JOIN citation ci ON ci.message_id = m.message_id WHERE m.conversation_id = 42;`
- **"What would you index?"** The foreign keys you search by (`conversation_id`, `user_id`) and anything unique
  (`email`).

### If they give you a *different* scenario
Don't panic. Use the 6-step recipe. Start small (3 or 4 tables), then grow. It's fine to say:
*"Let me start simple and add details as we go."*

---

## 5. System design interview (your project)

### 30-second version
"ClearPath has two parts. **Offline**, it reads the PDFs, splits them into sections, embeds them and stores them.
**Online**, when someone asks a question, it rewrites the question into official words, searches, sends the best 8
passages to GPT, and returns an answer with citations that the code checks."

### The big picture (draw this on the whiteboard)

```
 OFFLINE (run once, or when a form changes)
 ┌────────────┐   ┌────────────────┐   ┌──────────────┐   ┌────────────────┐
 │ USCIS PDFs │──▶│ Read + classify│──▶│ Chunk by     │──▶│ Embed (OpenAI) │──▶ Chroma vector DB
 │ (4 forms)  │   │ headings (font)│   │ section      │   │ 1536 numbers   │    + chunks.jsonl
 └────────────┘   └────────────────┘   └──────────────┘   └────────────────┘

 ONLINE (every question)
 ┌──────────┐   ┌─────────────┐   ┌──────────────────────────────────────────────────────┐
 │ Browser  │──▶│ Next.js     │──▶│ FastAPI  (Python)                                    │
 │ chat page│◀──│ (port 3000) │◀──│  1. Rewrite question → official terms   (GPT mini)   │
 └──────────┘   └─────────────┘   │  2. Search Chroma with original + rewrite             │
                 the OpenAI key   │  3. Form filter (if the user named a form)            │
                 never reaches    │  4. Send top 8 passages → GPT-4.1-mini (JSON answer)  │
                 the browser      │  5. Check citations in code, build source labels      │
                                  └──────────────────────────────────────────────────────┘
```

### Walk through one question (say this step by step)
Example: *"My green card application is still being processed. Can I work while I wait?"*
1. **Rewrite:** GPT turns it into "adjustment of status, Form I-485, employment authorization, Form I-765…"
2. **Search:** both the original and the rewrite are embedded and compared with the 466 chunks (cosine similarity).
3. **Filter:** if the user typed a form number like "I-485," only that form is searched.
4. **Answer:** the top 8 passages go to GPT-4.1-mini with strict rules: use only these passages, cite chunk IDs,
   and say "not covered" if the answer isn't there. The output is **structured JSON**.
5. **Verify:** the code rejects any cited ID that wasn't in the 8 passages, and builds the citation label (form,
   edition, page, section) **from the database, not from the AI's text**.
6. **Reply:** the answer, sources, warnings and cost go back to the page.

### Key design decisions (Decision → Why → Evidence)

| Decision | Why | Evidence |
|---|---|---|
| **RAG** instead of asking ChatGPT directly | Answers must come from the official text, with a source | Every answer has a citation, and out-of-scope questions are declined |
| **Chunk by section**, not every N words | Each passage answers one kind of question | Heading paths like "Who May File > Notes" |
| **Query rewriting** | Users say "green card"; the PDFs say "adjustment of status" | Plain-question Recall@5 went from 74% to 97% |
| **Keep the original question too** | Rewriting alone hurt jargon questions | Best MRR with original + rewrite |
| **Form filter uses the user's words only** | The AI once guessed the wrong form and the filter threw away the answer | Measured: filtering on the rewrite hurt |
| **8 passages** (not 5) | One correct passage ranked 7th | Fixed the translation question |
| **Hybrid search: tried, rejected** | It didn't help once rewriting existed | Measured: no gain |
| **Citations built by code** | AI text can be wrong; metadata can't be | Invalid citations show a warning |

### How do you know it works? (they WILL ask this)
- **Test set:** 82 questions, each asked in plain words and in jargon, plus 8 that it *should* refuse.
- **Retrieval metrics:** Recall@5 and MRR, which check whether the right passage is found and how high it ranks.
- **LLM-as-judge:** a stronger model (GPT-4.1) grades every answer against a reference answer.
- **Judge the judge:** I graded 15 answers blind myself and agreed with the judge 87% of the time.
- **Held-out questions:** I wrote new questions after tuning: 92% correct, and it answered one in Spanish.
- **Noise:** I ran setups more than once, because about 5% of grades change between identical runs.

### Likely questions (short answers)
- **"How do you stop hallucinations?"** Strict prompt, passages only, structured JSON, citations checked in code, and
  an "I don't know" path. Passages are treated as data, not instructions (a prompt-injection guard).
- **"What if USCIS updates a form?"** Download the new PDF and re-run ingestion. The edition date is stored with
  each chunk and shown in every citation, and the vector index rebuilds automatically when the chunks change (a
  fingerprint check).
- **"How would you scale to 10,000 users?"** The API is stateless, so I'd run several copies behind a load
  balancer. I'd move vectors to a managed vector DB or Postgres + pgvector, cache rewrites of common questions, add
  rate limits per user, and add a login.
- **"What does it cost?"** About $0.0013 per question. Building the whole index cost $0.002.
- **"Security and privacy?"** The OpenAI key stays on the server (Next.js forwards requests to Python). The API
  only listens on localhost. No personal data is stored today. Before going online, it needs a usage limit and a login.
- **"What was hardest?"** The vocabulary gap ("green card"), and a chunking bug where a rule about Form I-130A was
  buried at the end of another section. I fixed it by giving notes lists their own chunk.
- **"What would you do next?"** Follow-up questions (conversation memory), more forms, and testing with real users.
- **"Why not fine-tune a model?"** Forms change, and fine-tuning can't cite a page. RAG can be updated just by
  re-reading the PDF.

### Words to know (one line each)
- **Embedding:** a list of numbers that captures meaning; similar meanings give nearby numbers.
- **Vector database (Chroma):** stores embeddings and finds the closest ones fast.
- **Chunk:** one section of the instructions, the unit that gets searched.
- **RAG:** search first, then let the AI answer using only what was found.
- **Recall@5:** how often the right chunk is in the top 5 results.
- **MRR:** how high the first right result ranks, on average (1.0 means always first).
- **Structured output:** the AI must answer in a fixed JSON shape.
- **Cosine similarity:** how close two embeddings point in the same direction.

---

## 6. Day-of checklist

- [ ] Post the Teams message (part 1)
- [ ] Practice the 1-minute pitch out loud **twice**
- [ ] Memorize 3 numbers: **97% Recall@5, 95% correct, $0.0013 per question**
- [ ] Be able to draw the big-picture diagram from memory
- [ ] Practice drawing FORM → CHUNK → EMBEDDING (today) and USER → CONVERSATION → MESSAGE → CITATION plus
  USER → UPLOADED_FORM → FORM_ISSUE (the Postgres model), and explain why citations save a copy of the label
- [ ] Start both servers before the demo and test one question:
  - `.venv/Scripts/python -m immigration_helper.api`
  - `npm --prefix web run dev` → http://localhost:3000
- [ ] Have a backup: a screenshot of a good answer, in case the internet fails
- [ ] Remember: **talk out loud**, **start simple**, and it's OK to say *"let me think for a second"*
