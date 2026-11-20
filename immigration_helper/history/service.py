"""Asking questions inside a saved conversation, and reading old conversations back."""
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol

from immigration_helper.accounts import User
from immigration_helper.answering import PriorMessage
from immigration_helper.answering.assistant import Reply
from immigration_helper.history.models import Conversation, ConversationSummary

_MAX_TITLE_CHARS = 80


class ConversationNotFoundError(Exception):
    """The conversation doesn't exist or belongs to someone else (the caller can't tell which)."""


class QuestionAnswerer(Protocol):
    def ask(self, question: str, history: Sequence[PriorMessage] = ()) -> Reply: ...


class ConversationStore(Protocol):
    def list_for(self, user_id: int) -> list[ConversationSummary]:
        """The user's conversations, most recently updated first."""

    def load(self, user_id: int, conversation_id: int) -> Conversation | None:
        """The conversation with its messages in order, or None if the user doesn't own it."""

    def save_exchange(self, user_id: int, conversation_id: int | None, title: str, question: str,
                      reply: Reply) -> int:
        """Saves the question and the reply in one transaction, starting a new conversation (with this title) when
        conversation_id is None. Returns the conversation's ID. Raises ConversationNotFoundError if the user doesn't
        own the conversation."""


@dataclass(frozen=True)
class ChatTurn:
    conversation_id: int
    reply: Reply


class ChatService:
    def __init__(self, assistant: QuestionAnswerer, store: ConversationStore):
        self._assistant = assistant
        self._store = store

    def ask(self, user: User, question: str, conversation_id: int | None = None) -> ChatTurn:
        # Loading the conversation checks ownership before answering (so nobody pays for an answer that can't be
        # saved) and gives the agent the earlier messages, so follow-up questions make sense.
        history: tuple[PriorMessage, ...] = ()
        if conversation_id is not None:
            history = tuple(PriorMessage(message.role.value, message.content)
                            for message in self.conversation(user, conversation_id).messages)
        reply = self._assistant.ask(question, history)
        saved_id = self._store.save_exchange(user.user_id, conversation_id, title_for(question), question, reply)
        return ChatTurn(saved_id, reply)

    def conversations(self, user: User) -> list[ConversationSummary]:
        return self._store.list_for(user.user_id)

    def conversation(self, user: User, conversation_id: int) -> Conversation:
        conversation = self._store.load(user.user_id, conversation_id)
        if conversation is None:
            raise ConversationNotFoundError()
        return conversation


def title_for(question: str) -> str:
    """The first question, cut at a word boundary, names the conversation."""
    text = " ".join(question.split())
    if len(text) <= _MAX_TITLE_CHARS:
        return text
    return text[:_MAX_TITLE_CHARS].rsplit(" ", 1)[0] + "…"
