-- ClearPath for Immigration: PostgreSQL schema for users, chat history and uploaded-form review.
-- Passages and their embeddings stay in Chroma and data/index/chunks.jsonl; this database holds user data only.
--
-- Design decisions (agreed 2026-11-19):
--   * Login with email + password; only a password hash is stored. Emails are stored lowercase.
--   * Login sessions live in user_session (added when building the chat history).
--   * Questions and answers share one message table, ordered by time, with a role column.
--   * Citations keep a copy of the source label as the user saw it, because chunk IDs change when the PDFs are
--     re-chunked (the t36 fix shifted every I-130 chunk ID by one).
--   * Uploaded forms are read in memory and never kept: only the list of issues found is stored (2026-11-19;
--     the first design kept the PDF on disk).
--   * Deleting a user deletes everything they own (ON DELETE CASCADE), so users can remove their data.
--   * Personal values from uploaded forms (A-Number, SSN, ...) are never stored here; issues point to a location.

CREATE TABLE uscis_form (
    form_id      TEXT PRIMARY KEY CHECK (form_id ~ '^I-[0-9]{3}[A-Z]?$'),  -- e.g. 'I-485'
    title        TEXT NOT NULL,
    edition_date DATE NOT NULL
);

CREATE TABLE app_user (
    user_id       BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    email         TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- One row per logged-in browser. The cookie holds a random token; only its SHA-256 hash is stored, so a copy of the
-- database can't be used to log in. Logging out deletes the row.
CREATE TABLE user_session (
    token_hash TEXT PRIMARY KEY,
    user_id    BIGINT NOT NULL REFERENCES app_user (user_id) ON DELETE CASCADE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    expires_at TIMESTAMPTZ NOT NULL
);
CREATE INDEX user_session_by_user ON user_session (user_id);

CREATE TABLE conversation (
    conversation_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id         BIGINT NOT NULL REFERENCES app_user (user_id) ON DELETE CASCADE,
    title           TEXT NOT NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX conversation_by_user ON conversation (user_id, updated_at DESC);  -- "my chats, newest first"

CREATE TABLE message (
    message_id      BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    conversation_id BIGINT NOT NULL REFERENCES conversation (conversation_id) ON DELETE CASCADE,
    role            TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
    content         TEXT NOT NULL,
    reply_type      TEXT CHECK (reply_type IN ('answer', 'not_covered', 'conversation')),  -- assistant only
    search_query    TEXT,            -- assistant messages only: the agent's search queries, if it searched
    cost_usd        NUMERIC(10, 6),  -- assistant messages only
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK (role = 'assistant' OR (reply_type IS NULL AND search_query IS NULL AND cost_usd IS NULL)),
    CHECK (role = 'user' OR reply_type IS NOT NULL)
);
CREATE INDEX message_by_conversation ON message (conversation_id, created_at);  -- load a chat in order

CREATE TABLE citation (
    message_id BIGINT NOT NULL REFERENCES message (message_id) ON DELETE CASCADE,
    position   SMALLINT NOT NULL CHECK (position >= 1),  -- order shown under the answer
    form_id    TEXT NOT NULL REFERENCES uscis_form (form_id),
    chunk_id   TEXT NOT NULL,  -- for reference only: not stable across re-chunking
    label      TEXT NOT NULL,  -- snapshot, e.g. 'Form I-485 Instructions (09/18/26), p. 4: General Instructions'
    PRIMARY KEY (message_id, position)
);

CREATE TABLE uploaded_form (
    upload_id         BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id           BIGINT NOT NULL REFERENCES app_user (user_id) ON DELETE CASCADE,
    form_id           TEXT NOT NULL REFERENCES uscis_form (form_id),
    original_filename TEXT NOT NULL,  -- shown in the user's list; the file itself is not kept
    uploaded_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX uploaded_form_by_user ON uploaded_form (user_id, uploaded_at DESC);

CREATE TABLE form_issue (
    issue_id          BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    upload_id         BIGINT NOT NULL REFERENCES uploaded_form (upload_id) ON DELETE CASCADE,
    severity          TEXT NOT NULL CHECK (severity IN ('error', 'warning')),
    location          TEXT NOT NULL,  -- e.g. 'Part 2, Item Number 8'
    message           TEXT NOT NULL,  -- e.g. 'A-Number is empty' (never the value itself)
    instruction_label TEXT            -- the instruction passage behind the rule, if any
);
CREATE INDEX form_issue_by_upload ON form_issue (upload_id);
