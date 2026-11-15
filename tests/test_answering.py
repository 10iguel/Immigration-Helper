import json
from types import SimpleNamespace

import pytest

from immigration_helper.answering import Answerer, Citation
from immigration_helper.chat_model import ChatResult, ChatUsage, OpenAIChatModel
from immigration_helper.answering.prompt import build_messages
from immigration_helper.retrieval import ScoredChunk
from tests.factories import make_chunk

TRANSLATIONS = make_chunk(
    "If you submit a document with information in a foreign language, you must also submit a full English translation.",
    form="I-485", chunk_id="I-485-0009", heading="General Instructions",
)
BIRTH_CERTIFICATE = make_chunk(
    "Applicants must submit a photocopy of their birth certificate.",
    form="I-485", chunk_id="I-485-0021", heading="Birth Certificate",
)
NO_USAGE = ChatUsage(input_tokens=0, output_tokens=0, cost_usd=0.0)


class FixedRetriever:
    name = "fixed"

    def search(self, query: str, k: int) -> list[ScoredChunk]:
        return [ScoredChunk(TRANSLATIONS, 0.9), ScoredChunk(BIRTH_CERTIFICATE, 0.8)][:k]


class FakeChatModel:
    model = "fake"

    def __init__(self, reply: dict):
        self._reply = reply
        self.messages: list[dict] = []

    def complete_json(self, messages: list[dict], schema: dict, schema_name: str) -> ChatResult:
        self.messages = messages
        return ChatResult(self._reply, NO_USAGE)


def answer_with(reply: dict):
    return Answerer(FixedRetriever(), FakeChatModel(reply)).answer("Do I need to translate my birth certificate?")


def test_answer_cites_passages_with_labels_from_chunk_metadata():
    answer = answer_with({"answerable": True, "answer": "Yes.", "cited_chunk_ids": ["I-485-0009", "I-485-0009"]})

    assert answer.is_grounded
    assert answer.citations == (
        Citation("I-485-0009", "Form I-485 Instructions (08/21/25), p. 1: General Instructions"),
    )


def test_citations_not_among_the_passages_are_rejected():
    answer = answer_with({"answerable": True, "answer": "Yes.", "cited_chunk_ids": ["I-485-0009", "I-765-0042"]})

    assert answer.rejected_citation_ids == ("I-765-0042",)
    assert [citation.chunk_id for citation in answer.citations] == ["I-485-0009"]
    assert not answer.is_grounded


def test_unanswerable_question_is_not_grounded():
    answer = answer_with({"answerable": False, "answer": "The instructions don't cover this.", "cited_chunk_ids": []})

    assert not answer.answerable
    assert not answer.is_grounded


def test_prompt_shows_each_passage_with_its_id_and_the_question():
    messages = build_messages("Do I need a translation?", [TRANSLATIONS])

    assert messages[0]["role"] == "system"
    assert "[I-485-0009] Form I-485 Instructions > General Instructions" in messages[1]["content"]
    assert messages[1]["content"].endswith("Question: Do I need a translation?")


def fake_openai_client(message: SimpleNamespace, finish_reason: str = "stop") -> SimpleNamespace:
    completion = SimpleNamespace(
        choices=[SimpleNamespace(message=message, finish_reason=finish_reason)],
        usage=SimpleNamespace(prompt_tokens=1_000_000, completion_tokens=500_000),
    )
    return SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=lambda **_: completion)))


def test_openai_chat_model_parses_json_and_prices_tokens():
    reply = {"answerable": True, "answer": "Yes.", "cited_chunk_ids": []}
    client = fake_openai_client(SimpleNamespace(content=json.dumps(reply), refusal=None))

    result = OpenAIChatModel("gpt-4.1-mini", client).complete_json([], {}, "grounded_answer")

    assert result.content == reply
    assert result.usage.cost_usd == pytest.approx(0.40 + 0.80)


def test_openai_chat_model_raises_on_refusal():
    client = fake_openai_client(SimpleNamespace(content=None, refusal="I can't help with that."))

    with pytest.raises(RuntimeError, match="refused"):
        OpenAIChatModel("gpt-4.1-mini", client).complete_json([], {}, "grounded_answer")


def test_openai_chat_model_raises_on_truncated_reply():
    client = fake_openai_client(SimpleNamespace(content='{"answerable": tr', refusal=None), finish_reason="length")

    with pytest.raises(RuntimeError, match="stopped early"):
        OpenAIChatModel("gpt-4.1-mini", client).complete_json([], {}, "grounded_answer")


def test_unknown_chat_model_is_rejected():
    with pytest.raises(ValueError):
        OpenAIChatModel("gpt-unknown", client=SimpleNamespace())
