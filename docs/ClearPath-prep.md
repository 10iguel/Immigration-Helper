# ClearPath for Immigration: Pitch and Interview Prep

> **How to use this page:** read one part at a time. Each part starts with a 30-second version.
> Everything here is true about your project as of 2026-11-19 (search agent, login and chat history included).

**Contents**
1. [Teams post](#1-teams-post-copy-and-paste)
2. [The 1-minute spoken pitch](#2-the-1-minute-spoken-pitch)
3. [Numbers to remember](#3-numbers-to-remember)
4. [Data modeling interview](#4-live-data-modeling-interview)
5. [System design interview](#5-system-design-interview-your-project)
6. [Limits per user](#6-limits-per-user)
7. [Day-of checklist](#7-day-of-checklist)

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

Say it in this order (**Problem → Solution → Proof → Demo → Ask**):

1. **Problem:** "Immigration instructions are long and full of legal words. People ask about a 'green card,' but the
   instructions say 'adjustment of status,' so normal search doesn't find the answer."
2. **Solution:** "ClearPath is an AI agent with one tool: a search over the official instructions. It decides when to
   search, writes the search in official terms, and answers in plain words with a citation. If the answer isn't
   there, it says so. You log in, and your chats are saved, so you can ask follow-up questions."
3. **Proof:** "On 77 test questions it's 96% correct, it searched before every answer, and an answer with no source
   is blocked in code. Each answer costs about two tenths of a cent."
4. **Demo** (if you can): ask *"I'm a US citizen. Can I sponsor my brother?"*, then *"What about my mom?"*, then
   *"awesome, thanks!"*. That shows search, follow-up memory and small talk in 30 seconds.
5. **Ask:** "I'd love feedback: what immigration questions would *you* want it to answer?"

---

## 3. Numbers to remember

Learn these. They make you sound like you measured everything, because you did.

| What | Number |
|---|---|
| Forms covered | 4 (I-130, I-131, I-485, I-765) |
| Chunks (searchable passages) | 466 |
| Test messages | 88 (37 plain, 37 jargon, 8 out of scope, 3 small talk, 3 follow-ups) |
| Right passage in top 5 (Recall@5) | 97% (was 74% for plain questions before official vocabulary) |
| Answers correct (search agent) | **96%** of 77 answerable (jargon 100%) |
| Searched before answering | **100%** of answerable questions |
| Answers invented from memory | **0** (blocked in code) |
| Judge vs. me (human check) | Agreed on 13 of 15 (87%) |
| Cost per question | about **$0.0019** (small talk: $0.0005) |
| Passages per search / searches per message | 8 / at most 2 |
| Form review (I-765) | 11 checks; 17 planted mistakes all found; 0 false alarms on a correct form |

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
| **Lookup / enum** | Reply type: answer, not covered, conversation | A small lookup table or a CHECK constraint |

**Normalization in one sentence:** "Every fact is stored once." If you'd copy the same value into many rows
(such as a form's title in every chunk), move it to its own table.

### Practice: model YOUR project
This is very likely to come up. Here's your real data, drawn as tables.

**The instructions and the test set** (stored in JSON/JSONL files plus Chroma):

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
form_id   FK              phrase                        target_id   FK (NULL = out of scope or small talk)
reference_answer                                        style  (plain / jargon / out_of_scope / ...)
                                                        previous_question (follow-ups only)
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

**The PostgreSQL model: users, logins, chat history and (soon) form review.** It's running in Docker, and the
full SQL is in [`db/schema.sql`](../db/schema.sql).

```
APP_USER 1──N USER_SESSION
APP_USER 1──N CONVERSATION 1──N MESSAGE 1──N CITATION N──1 USCIS_FORM
APP_USER 1──N UPLOADED_FORM 1──N FORM_ISSUE          (form review: built for Form I-765)
USCIS_FORM 1──N UPLOADED_FORM
```

| Table | Key columns |
|---|---|
| `app_user` | user_id PK, email UNIQUE (stored lowercase), password_hash (scrypt) |
| `user_session` | token_hash PK (SHA-256 of the cookie token), user_id FK, expires_at |
| `conversation` | conversation_id PK, user_id FK, title, updated_at |
| `message` | message_id PK, conversation_id FK, role (user/assistant), content, **reply_type** (answer / not_covered / conversation), search_query, cost_usd |
| `citation` | PK (message_id, position), form_id FK, chunk_id, label (a saved copy) |
| `uscis_form` | form_id PK ('I-485'), title, edition_date (filled from the PDFs when the API starts) |
| `uploaded_form` | upload_id PK, user_id FK, form_id FK, original_filename, uploaded_at (no file is stored) |
| `form_issue` | issue_id PK, upload_id FK, severity, location ('Part 2, Item 8'), message |

**The decisions, and how to say them:**
1. "Questions and answers share **one `message` table** with a `role` column, because a chat is just an ordered list
   of messages."
2. "**Citations save a copy of the label**, not a foreign key to a chunk, because chunk IDs change when I re-chunk.
   My t36 fix shifted every I-130 chunk ID by one, so old chats would have pointed to the wrong passage."
3. "Chunks and vectors **stay in Chroma**. Postgres holds only user data, plus the small `uscis_form` lookup table."
4. "**Only hashes are stored for secrets.** Passwords are hashed with scrypt (salted), and login tokens with SHA-256,
   so a stolen copy of the database can't be used to log in."
5. "**`reply_type` replaced a yes/no `answerable` column.** The agent has three kinds of replies, and 'answerable'
   can be computed from `reply_type`, so keeping both would store the same fact twice. I wrote a small migration,
   so old chats were kept."
6. "**ON DELETE CASCADE** from the user down, so a user can delete all their immigration data at once. I tested it:
   deleting a user removed their chats, messages and citations."
7. "**Uploaded forms are never kept.** My first design saved the PDF on disk, but the review finishes right away, so
   I read the PDF in memory and store only the problems. An issue says 'Part 2, Item 8 is empty', never the A-Number
   itself. Less data stored means less data that can leak." (A second migration dropped the file columns.)

**Indexes, and why:** `message (conversation_id, created_at)` loads a chat in order; `conversation (user_id,
updated_at DESC)` lists "my chats, newest first"; `email` and `token_hash` are unique, so they're indexed
automatically.

**CHECK constraints worth mentioning:** a user message can't have a `reply_type` or a cost, and an assistant message
must have a `reply_type`. The database enforces it, so bad data can't get in even if the code has a bug.

### Questions they may ask (with short answers)
- **"Why not put everything in one table?"** It would repeat data and cause update mistakes. If a form's
  edition changes, I'd have to fix 466 rows instead of 1.
- **"SQL or NoSQL here?"** SQL for users, chats and citations, because they have clear relationships. A vector
  database for embeddings, because it's built for similarity search. The instruction chunks are a JSON file because
  they're read-only and rebuilt from the PDFs.
- **"What does a query look like?"** "All sources cited in a conversation":
  `SELECT DISTINCT ci.label FROM message m JOIN citation ci ON ci.message_id = m.message_id WHERE m.conversation_id = 42;`
- **"How do you stop one user reading another user's chat?"** Every query filters by the logged-in `user_id`
  (`WHERE conversation_id = %s AND user_id = %s`). Someone else's chat gets a 404, the same as a chat that doesn't
  exist, so you can't even tell it exists.
- **"Why no ORM?"** My backend is Python, and I kept all the SQL in one `storage` package. For a database class I
  wanted to show the SQL myself, and it's tested against the real Postgres.

### If they give you a *different* scenario
Don't panic. Use the 6-step recipe. Start small (3 or 4 tables), then grow. It's fine to say:
*"Let me start simple and add details as we go."*

---

## 5. System design interview (your project)

### 30-second version
"ClearPath has two parts. **Offline**, it reads the PDFs, splits them into sections, embeds them and stores them in
Chroma. **Online**, a logged-in user sends a message. An **AI agent with one tool, a search over the instructions**,
decides whether to search, writes the search query using the chat history, and answers only from the passages it
found. Code checks every citation and blocks answers with no source. The question and answer are saved in
PostgreSQL."

### The big picture (draw this on the whiteboard)

```
 OFFLINE (run once, or when a form changes)
 ┌────────────┐   ┌────────────────┐   ┌──────────────┐   ┌────────────────┐
 │ USCIS PDFs │──▶│ Read + classify│──▶│ Chunk by     │──▶│ Embed (OpenAI) │──▶ Chroma vector DB
 │ (4 forms)  │   │ headings (font)│   │ section      │   │ 1536 numbers   │    + chunks.jsonl
 └────────────┘   └────────────────┘   └──────────────┘   └────────────────┘

 ONLINE (every message)
 ┌──────────┐   ┌─────────────┐   ┌─────────────────────────────────────────────────┐   ┌──────────────┐
 │ Browser  │──▶│ Next.js     │──▶│ FastAPI (Python)                                │──▶│ PostgreSQL   │
 │ chat page│◀──│ server      │◀──│  1. Check the login cookie                      │◀──│ users, chats │
 └──────────┘   └─────────────┘   │  2. Load the chat's last 6 messages             │   └──────────────┘
  HttpOnly        forwards /api/* │  3. SEARCH AGENT (GPT-4.1-mini)                 │
  login cookie    the OpenAI key  │       └─ tool: search_instructions(query) ──────┼──▶ Chroma
                  never reaches   │  4. Check citations in code; block no-source    │
                  the browser     │  5. Save question + answer + citations          │
                                  └─────────────────────────────────────────────────┘
```

### Walk through a follow-up question (say this step by step)
Earlier: *"I'm a US citizen. Can I sponsor my brother?"* Now: *"What about my mom?"*
1. **Login:** FastAPI reads the HttpOnly cookie, hashes the token, and finds the user in `user_session`.
2. **History:** it loads this chat (only if it belongs to this user) and sends the last 6 messages to the agent.
3. **Decide:** the agent sees that this is an immigration question, so it **must search**. Small talk like "thanks!"
   gets a short reply with no search.
4. **Search:** the agent writes the query itself, using the history: *"U.S. citizen petitioner, petition for
   mother, Form I-130"*. The tool searches with the user's words plus that query and returns the top 8 passages. If
   the user typed a form number, only that form is searched.
5. **Answer:** the agent replies in a fixed JSON shape: `reply_type` (answer / not_covered / conversation), the text,
   and the IDs of the passages it used. It may search a second time first, but no more than twice.
6. **Verify in code:** cited IDs must come from this message's searches, labels are built from the chunk metadata,
   and **an answer with no valid source is replaced** by "I couldn't find this… I won't guess."
7. **Save and reply:** the question, answer, citations, search query and cost are saved in one transaction, and the
   page shows the answer with its sources.

### Key design decisions (Decision → Why → Evidence)

| Decision | Why | Evidence |
|---|---|---|
| **RAG** instead of asking ChatGPT directly | Answers must come from the official text, with a source | Every answer cites its passage |
| **Chunk by section**, not every N words | Each passage answers one kind of question | Heading paths like "Who May File > Notes" |
| **Official vocabulary in the search** | Users say "green card"; the PDFs say "adjustment of status" | Plain-question Recall@5 went from 74% to 97% |
| **Search with the user's words + the AI's query** | The query alone hurt jargon questions | Best MRR with both |
| **A search agent (tool calling)** instead of a fixed pipeline | "thanks!" was searched and answered "not covered"; follow-ups didn't work | Small talk 3/3, follow-ups 2/3 (+1 partial), still 96% correct |
| **Grounding enforced in code** | The agent once answered from memory (Form I-90) | 0 invented answers after the guard |
| **Form filter uses the user's words only** | AI text once named the wrong form and the filter threw away the answer | Measured: filtering on AI text hurt |
| **8 passages** per search, at most 2 searches | One correct passage ranked 7th; a hard limit caps cost | Fixed the translation question |
| **Hybrid search: tried, rejected** | It didn't help once official vocabulary was in the query | Measured: no gain |
| **Login with HttpOnly cookie + hashed session token** | Page JavaScript can't steal the cookie; a stolen database can't log anyone in | Tested in the browser |
| **Python owns the database (no Prisma)** | One language for all business logic; SQL in one package | 3 tests run the real SQL on Postgres |

### How do you know it works? (they WILL ask this)
- **Test set:** 88 messages: each topic in plain words and in jargon, plus questions it *should* refuse, small talk,
  and follow-ups asked after an earlier question in the same chat.
- **Retrieval metrics:** Recall@5 and MRR, which check whether the right passage is found and how high it ranks.
- **LLM-as-judge:** a stronger model (GPT-4.1) grades every answer against a reference answer.
- **Judge the judge:** I graded 15 answers blind myself and agreed with the judge 87% of the time.
- **Rules in code:** an out-of-scope question only counts as correct if the agent **searched** and then declined;
  small talk only if it did **not** search.
- **Held-out questions:** questions written after tuning got 92% (before the agent).
- **Noise:** I run setups more than once, because about 5% of grades change between identical runs.
- **85 automated tests**, including the real SQL against Postgres in a throwaway schema.

### Likely questions (short answers)
- **"How do you stop hallucinations?"** Five layers: (1) the agent must search before any immigration answer;
  (2) it may only use passages from this message's searches; (3) a fixed JSON shape; (4) code checks every citation;
  (5) an answer with no valid source is **replaced before anyone sees it**. Passages are treated as data, not
  instructions (a prompt-injection guard).
- **"Why tool calling instead of always searching?"** Always searching made "thanks!" cost a search and come back as
  "not covered", and a follow-up like "what about my mom?" was searched on its own. With a tool, the model decides
  when to search and writes the query with the chat history in mind.
- **"Isn't it risky to let the model decide?"** Yes, so I measured it: it searched before 100% of the answerable
  questions. The first run caught one answer from memory, so I added the code guard. That's why the guard is in
  code, not just in the prompt.
- **"What's still not perfect?"** For questions like "how much is the fee?", the reply correctly says the
  instructions don't give it (they point to Form G-1055), but it's labeled `answer` instead of `not_covered`. The
  content is right; the label is off. Out-of-scope scored 3 of 8 under my strict rule.
- **"What if USCIS updates a form?"** Download the new PDF and re-run ingestion. The edition date is stored with
  each chunk and shown in every citation, and the vector index rebuilds automatically when the chunks change.
- **"How would you scale to 10,000 users?"** The API keeps no state between requests (chats are in Postgres), so I'd
  run several copies behind a load balancer, use a connection pool, move vectors to a managed vector DB or Postgres +
  pgvector, and add per-user limits (see part 6).
- **"What does it cost?"** About $0.0019 per question and $0.0005 for small talk. Building the whole index cost $0.002.
- **"Security and privacy?"** The OpenAI key stays on the server. Passwords and login tokens are only stored as
  hashes. Every chat query checks the owner. The API only listens on localhost. Deleting a user deletes all their data.
- **"What was hardest?"** The vocabulary gap ("green card"), a chunking bug where a rule about Form I-130A was
  buried at the end of another section, and catching the agent answering from memory.
- **"How does form review work? Is it AI?"** No, on purpose. The I-765 is a fillable PDF with 161 named fields,
  so code reads exactly what was typed and 11 fixed rules check it (one reason selected, a real mm/dd/yyyy birth
  date, a 9-digit A-Number…). Each rule cites the instruction it comes from. An AI could miss an error or invent
  one, and on a legal form either could hurt someone. I tested it with 17 planted mistakes on fake forms: all found,
  each at exactly its location, and a correct form gets no complaints.
- **"What would you do next?"** Per-user usage limits, more forms in the review (I-130, I-485), and testing with
  real users.
- **"Why not fine-tune a model?"** Forms change, and fine-tuning can't cite a page. RAG can be updated just by
  re-reading the PDF.

### Words to know (one line each)
- **Embedding:** a list of numbers that captures meaning; similar meanings give nearby numbers.
- **Vector database (Chroma):** stores embeddings and finds the closest ones fast.
- **Chunk:** one section of the instructions, the unit that gets searched.
- **RAG:** search first, then let the AI answer using only what was found.
- **Agent / tool calling:** the AI can ask the program to run a function (here, a search) and then use the result.
- **Grounding:** every fact in an answer comes from a source the system can point to.
- **Recall@5:** how often the right chunk is in the top 5 results.
- **MRR:** how high the first right result ranks, on average (1.0 means always first).
- **Structured output:** the AI must answer in a fixed JSON shape.
- **HttpOnly cookie:** a cookie the browser sends automatically but page JavaScript can't read.
- **Hash:** a one-way fingerprint; you can check a password against it, but you can't turn it back into the password.

---

## 6. Limits per user

### 30-second version
"Each message has hard limits (length, number of searches, how much history the agent sees), but there's **no limit
yet on how many messages a user can send**. That's fine while it only runs on my computer, but it's the first thing
I'd add before putting it online, because every message is paid with my OpenAI key."

### Limits that exist today

| What | Limit | Where it's set |
|---|---|---|
| Question length | 1 to 1,000 characters (the page and the API both check) | `api/app.py`, `web/lib/api.ts` |
| Searches per message | at most **2** | `answering/agent.py` (`MAX_SEARCHES`) |
| Passages per search | **8** | `config.py` (`ANSWER_PASSAGES`) |
| Chat history the agent sees | last **6 messages** (3 questions + 3 answers) | `answering/agent.py` (`HISTORY_MESSAGES`) |
| Reply length | at most **800 tokens** (about 600 words) per model call | `chat_model.py` |
| Login session | **14 days**, then log in again | `accounts/service.py` |
| Password | **8 to 200** characters | `accounts/passwords.py` |
| Email | up to **254** characters, one account per email | `accounts/models.py` + UNIQUE in the database |
| Chat title | first **80** characters of the first question | `history/service.py` |
| Uploaded form | PDF only, at most **5 MB**, Form I-765 only; read in memory, never stored | `review/service.py` |

So the **most one message can cost** is about 3 model calls (2 searches + the reply), roughly **$0.005**.

### Limits that do NOT exist yet (be honest about these)
- **Messages per user per day:** unlimited. One user could send thousands of questions.
- **Spending per user:** unlimited.
- **Sign-ups:** anyone who can reach the page can create accounts.
- **Wrong-password attempts:** unlimited (no lockout), so passwords could be guessed slowly.
- **Number of chats per user:** unlimited (cheap, so it doesn't really matter).

### How you'd add the important one (say this if asked)
"The data is already there: every assistant message stores its `cost_usd` and `created_at`. Before answering, I'd
run one query, *how many messages (or how many dollars) has this user used today?*, and return **429 Too Many
Requests** if it's over the limit, for example **50 messages or $0.10 per day**. Because the check happens *before*
the agent runs, a blocked request costs nothing."

```sql
SELECT count(*) AS messages, coalesce(sum(m.cost_usd), 0) AS spent
FROM message m JOIN conversation c ON c.conversation_id = m.conversation_id
WHERE c.user_id = %s AND m.role = 'assistant' AND m.created_at > now() - interval '1 day';
```

---

## 7. Day-of checklist

- [ ] Post the Teams message (part 1)
- [ ] Practice the 1-minute pitch out loud **twice**
- [ ] Memorize 3 numbers: **97% Recall@5, 96% correct, $0.0019 per question**
- [ ] Be able to draw the big-picture diagram from memory, including the **agent and its search tool**
- [ ] Practice drawing FORM → CHUNK → EMBEDDING (Chroma) and USER → CONVERSATION → MESSAGE → CITATION (Postgres),
  and explain why citations save a copy of the label and why `reply_type` replaced `answerable`
- [ ] Know your limits (part 6), including the one that's missing: messages per user per day
- [ ] Start everything before the demo and test one question:
  - Docker Desktop open, then `docker compose up -d`
  - `.venv/Scripts/python -m immigration_helper.api`
  - `npm --prefix web run dev` → http://localhost:3000
  - Demo: "Can I sponsor my brother?" → "What about my mom?" → "awesome, thanks!"
- [ ] Have a backup: a screenshot of a good answer, in case the internet fails
- [ ] Remember: **talk out loud**, **start simple**, and it's OK to say *"let me think for a second"*
