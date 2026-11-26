"""Runs the real SQL against PostgreSQL (docker compose up -d). Each test gets its own throwaway schema, so the
development data is never touched. Skipped when the database isn't running."""
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import psycopg
import pytest
from psycopg import sql

from immigration_helper import config
from immigration_helper.accounts import EmailAddress, EmailTakenError
from immigration_helper.answering import ReplyKind
from immigration_helper.history import ConversationNotFoundError, MessageRole
from immigration_helper.models import FormId
from immigration_helper.review import Issue, Severity
from immigration_helper.storage import (
    Database,
    PostgresConversationStore,
    PostgresReviewStore,
    PostgresUserStore,
    sync_forms,
)
from tests.factories import make_chunk
from tests.fakes import PASSAGE, make_reply

SCHEMA_SQL = Path("db/schema.sql").read_text(encoding="utf-8")


@pytest.fixture
def database():
    schema = f"test_{uuid.uuid4().hex[:12]}"
    try:
        admin = psycopg.connect(config.DATABASE_URL, autocommit=True, connect_timeout=3)
    except psycopg.OperationalError:
        pytest.skip("PostgreSQL is not running (start it with: docker compose up -d)")
    with admin:
        admin.execute(sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(schema)))
        try:
            test_database = Database(config.DATABASE_URL, schema)
            with test_database.connect() as connection:
                connection.execute(SCHEMA_SQL)
            sync_forms(test_database, [PASSAGE, make_chunk("x", form="I-765", chunk_id="I-765-0001")])
            yield test_database
        finally:
            admin.execute(sql.SQL("DROP SCHEMA {} CASCADE").format(sql.Identifier(schema)))


def test_users_and_sessions(database):
    users = PostgresUserStore(database)
    user = users.add_user(EmailAddress("ana@example.com"), "hash")
    now = datetime.now(timezone.utc)
    users.add_session("token-hash", user.user_id, now + timedelta(days=1))
    users.add_session("old-token-hash", user.user_id, now - timedelta(seconds=1))

    assert users.find_credentials(EmailAddress("ANA@example.com")) == (user, "hash")
    assert users.user_for_session("token-hash", now) == user
    assert users.user_for_session("old-token-hash", now) is None  # expired
    with pytest.raises(EmailTakenError):
        users.add_user(EmailAddress("ana@example.com"), "other hash")
    users.delete_session("token-hash")
    assert users.user_for_session("token-hash", now) is None


def test_exchanges_are_saved_in_order_with_their_citations(database):
    users, conversations = PostgresUserStore(database), PostgresConversationStore(database)
    ana = users.add_user(EmailAddress("ana@example.com"), "hash")
    bo = users.add_user(EmailAddress("bo@example.com"), "hash")

    chat = conversations.save_exchange(ana.user_id, None, "Translations", "Do I need a translation?",
                                       make_reply("Do I need a translation?"))
    conversations.save_exchange(ana.user_id, chat, "ignored", "Who can translate it?", make_reply("Who?", "Anyone."))

    loaded = conversations.load(ana.user_id, chat)
    assert loaded.title == "Translations"
    assert [(m.role, m.content) for m in loaded.messages] == [
        (MessageRole.USER, "Do I need a translation?"),
        (MessageRole.ASSISTANT, "Yes, submit a full English translation."),
        (MessageRole.USER, "Who can translate it?"),
        (MessageRole.ASSISTANT, "Anyone."),
    ]
    assert loaded.messages[1].sources == (make_reply("x").answer.citations[0].label,)
    assert loaded.messages[1].cost_usd == pytest.approx(0.0013)
    assert loaded.messages[0].cost_usd is None and loaded.messages[0].kind is None
    assert loaded.messages[1].kind is ReplyKind.ANSWER
    with database.connect() as connection:
        queries = connection.execute("SELECT search_query FROM message WHERE role = 'assistant'").fetchall()
    assert [row["search_query"] for row in queries] == ["translation requirements"] * 2
    assert [summary.title for summary in conversations.list_for(ana.user_id)] == ["Translations"]

    # Another user can't see, continue or list it.
    assert conversations.load(bo.user_id, chat) is None
    assert conversations.list_for(bo.user_id) == []
    with pytest.raises(ConversationNotFoundError):
        conversations.save_exchange(bo.user_id, chat, "x", "Hi", make_reply("Hi"))
    assert len(conversations.load(ana.user_id, chat).messages) == 4  # the failed save left nothing behind


def test_deleting_a_user_deletes_their_conversations(database):
    users, conversations = PostgresUserStore(database), PostgresConversationStore(database)
    ana = users.add_user(EmailAddress("ana@example.com"), "hash")
    chat = conversations.save_exchange(ana.user_id, None, "Translations", "Q?", make_reply("Q?"))

    with database.connect() as connection:
        connection.execute("DELETE FROM app_user WHERE user_id = %s", (ana.user_id,))
        remaining = connection.execute("SELECT count(*) AS n FROM message WHERE conversation_id = %s",
                                       (chat,)).fetchone()["n"]

    assert remaining == 0


def test_reviews_keep_issues_count_them_and_belong_to_one_user(database):
    users, reviews = PostgresUserStore(database), PostgresReviewStore(database)
    ana = users.add_user(EmailAddress("ana@example.com"), "hash")
    bo = users.add_user(EmailAddress("bo@example.com"), "hash")
    issues = [Issue(Severity.ERROR, "Part 2, Item Number 16", "The date of birth is empty.", "Form I-765 Instructions"),
              Issue(Severity.WARNING, "Part 2, Item Number 8", "The A-Number is empty.")]

    saved = reviews.save(ana.user_id, FormId("I-765"), "i765.pdf", issues)
    clean = reviews.save(ana.user_id, FormId("I-765"), "fixed.pdf", [])

    assert (saved.errors, saved.warnings) == (1, 1)
    assert [(s.filename, s.errors, s.warnings) for s in reviews.list_for(ana.user_id)] == [
        ("fixed.pdf", 0, 0), ("i765.pdf", 1, 1)]
    assert reviews.load(ana.user_id, saved.review_id).issues == tuple(issues)
    assert reviews.load(bo.user_id, saved.review_id) is None
    assert not reviews.delete(bo.user_id, saved.review_id)
    assert reviews.delete(ana.user_id, saved.review_id)
    assert [s.review_id for s in reviews.list_for(ana.user_id)] == [clean.review_id]
