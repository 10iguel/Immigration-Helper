"""Conversations, messages and citations in PostgreSQL."""
from collections import defaultdict

from immigration_helper.answering import ReplyKind
from immigration_helper.answering.assistant import Reply
from immigration_helper.history import (
    Conversation,
    ConversationNotFoundError,
    ConversationSummary,
    MessageRole,
    StoredMessage,
)
from immigration_helper.storage.database import Database


class PostgresConversationStore:
    def __init__(self, database: Database):
        self._database = database

    def list_for(self, user_id: int) -> list[ConversationSummary]:
        with self._database.connect() as connection:
            rows = connection.execute(
                "SELECT conversation_id, title, updated_at FROM conversation WHERE user_id = %s "
                "ORDER BY updated_at DESC, conversation_id DESC",
                (user_id,),
            ).fetchall()
        return [ConversationSummary(row["conversation_id"], row["title"], row["updated_at"]) for row in rows]

    def load(self, user_id: int, conversation_id: int) -> Conversation | None:
        # Three queries (conversation, messages, citations) instead of one query per message.
        with self._database.connect() as connection:
            header = connection.execute(
                "SELECT title FROM conversation WHERE conversation_id = %s AND user_id = %s",
                (conversation_id, user_id),
            ).fetchone()
            if header is None:
                return None
            messages = connection.execute(
                "SELECT message_id, role, content, reply_type, cost_usd, created_at FROM message "
                "WHERE conversation_id = %s ORDER BY created_at, message_id",
                (conversation_id,),
            ).fetchall()
            citations = connection.execute(
                "SELECT c.message_id, c.label FROM citation c JOIN message m ON m.message_id = c.message_id "
                "WHERE m.conversation_id = %s ORDER BY c.message_id, c.position",
                (conversation_id,),
            ).fetchall()

        labels: dict[int, list[str]] = defaultdict(list)
        for citation in citations:
            labels[citation["message_id"]].append(citation["label"])
        return Conversation(conversation_id, header["title"], tuple(
            StoredMessage(
                role=MessageRole(row["role"]),
                content=row["content"],
                created_at=row["created_at"],
                kind=ReplyKind(row["reply_type"]) if row["reply_type"] else None,
                sources=tuple(labels[row["message_id"]]),
                cost_usd=float(row["cost_usd"]) if row["cost_usd"] is not None else None,
            )
            for row in messages
        ))

    def save_exchange(self, user_id: int, conversation_id: int | None, title: str, question: str,
                      reply: Reply) -> int:
        with self._database.connect() as connection:
            if conversation_id is None:
                row = connection.execute(
                    "INSERT INTO conversation (user_id, title) VALUES (%s, %s) RETURNING conversation_id",
                    (user_id, title),
                ).fetchone()
            else:
                row = connection.execute(
                    "UPDATE conversation SET updated_at = now() WHERE conversation_id = %s AND user_id = %s "
                    "RETURNING conversation_id",
                    (conversation_id, user_id),
                ).fetchone()
                if row is None:
                    raise ConversationNotFoundError()
            saved_id = row["conversation_id"]

            connection.execute(
                "INSERT INTO message (conversation_id, role, content) VALUES (%s, %s, %s)",
                (saved_id, MessageRole.USER.value, question),
            )
            answer = reply.answer
            assistant_message_id = connection.execute(
                "INSERT INTO message (conversation_id, role, content, reply_type, search_query, cost_usd) "
                "VALUES (%s, %s, %s, %s, %s, %s) RETURNING message_id",
                (saved_id, MessageRole.ASSISTANT.value, answer.text, answer.kind.value, reply.search_query or None,
                 reply.cost_usd),
            ).fetchone()["message_id"]
            with connection.cursor() as cursor:
                cursor.executemany(
                    "INSERT INTO citation (message_id, position, form_id, chunk_id, label) VALUES (%s, %s, %s, %s, %s)",
                    [(assistant_message_id, position, citation.form.value, citation.chunk_id, citation.label)
                     for position, citation in enumerate(answer.citations, start=1)],
                )
        return saved_id
