"""Saved conversations, as the user sees them."""
from dataclasses import dataclass
from datetime import datetime
from enum import Enum

from immigration_helper.answering import ReplyKind


class MessageRole(Enum):
    USER = "user"
    ASSISTANT = "assistant"


@dataclass(frozen=True)
class ConversationSummary:
    conversation_id: int
    title: str
    updated_at: datetime


@dataclass(frozen=True)
class StoredMessage:
    role: MessageRole
    content: str
    created_at: datetime
    kind: ReplyKind | None = None  # assistant messages only
    sources: tuple[str, ...] = ()  # citation labels as the user saw them
    cost_usd: float | None = None  # assistant messages only


@dataclass(frozen=True)
class Conversation:
    conversation_id: int
    title: str
    messages: tuple[StoredMessage, ...]
