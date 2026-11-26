import pytest

from immigration_helper.accounts import EmailAddress, User
from immigration_helper.answering import PriorMessage
from immigration_helper.history import ChatService, ConversationNotFoundError, MessageRole
from immigration_helper.history.service import title_for
from tests.fakes import InMemoryConversationStore, StubAssistant

ANA = User(1, EmailAddress("ana@example.com"))
BO = User(2, EmailAddress("bo@example.com"))


def test_first_question_starts_a_conversation_named_after_it_and_later_ones_continue_it():
    assistant = StubAssistant()
    chats = ChatService(assistant, InMemoryConversationStore())

    first = chats.ask(ANA, "Do I need a translation?")
    second = chats.ask(ANA, "What about my marriage certificate?", first.conversation_id)

    assert second.conversation_id == first.conversation_id
    conversation = chats.conversation(ANA, first.conversation_id)
    assert conversation.title == "Do I need a translation?"
    assert [message.role for message in conversation.messages] == [MessageRole.USER, MessageRole.ASSISTANT] * 2
    assert conversation.messages[1].sources == (first.reply.answer.citations[0].label,)
    # The follow-up was answered with the earlier messages as context.
    assert assistant.histories == [(), (PriorMessage("user", "Do I need a translation?"),
                                       PriorMessage("assistant", "Yes, submit a full English translation."))]


def test_someone_elses_conversation_is_not_found_and_no_answer_is_paid_for():
    assistant = StubAssistant()
    chats = ChatService(assistant, InMemoryConversationStore())
    anas = chats.ask(ANA, "Do I need a translation?").conversation_id

    with pytest.raises(ConversationNotFoundError):
        chats.ask(BO, "Can I read Ana's chat?", anas)
    with pytest.raises(ConversationNotFoundError):
        chats.conversation(BO, anas)
    assert assistant.questions == ["Do I need a translation?"]
    assert chats.conversations(BO) == []


def test_long_questions_are_cut_at_a_word_for_the_title():
    title = title_for("I have a green card and need to live abroad for about 18 months for work. How do I come back?")

    assert len(title) <= 81
    assert title.endswith("…")
    assert title.startswith("I have a green card")
    assert title_for("  short   question ") == "short question"
