import pytest
from fastapi.testclient import TestClient
from openai import APIConnectionError

from immigration_helper.answering import Answer, Answerer, Citation
from immigration_helper.answering.assistant import Assistant, Reply
from immigration_helper.api import create_app
from immigration_helper.chat_model import ChatResult, ChatUsage
from immigration_helper.retrieval import EmbeddingUsage, QueryRewriter, RewritingRetriever, ScoredChunk
from tests.factories import make_chunk

PASSAGE = make_chunk("You must also submit a full English translation.", form="I-485", chunk_id="I-485-0009")
REWRITE_USAGE = ChatUsage(100, 20, 0.001)
ANSWER_USAGE = ChatUsage(1000, 100, 0.002)


class FixedChatModel:
    model = "fake"

    def __init__(self, content: dict, usage: ChatUsage):
        self._content, self._usage = content, usage

    def complete_json(self, messages: list[dict], schema: dict, schema_name: str) -> ChatResult:
        return ChatResult(self._content, self._usage)


class FixedRetriever:
    name = "fixed"

    def search(self, query: str, k: int) -> list[ScoredChunk]:
        return [ScoredChunk(PASSAGE, 0.9)]


class FreeEmbedder:
    model = "fake"

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [[1.0] for _ in texts]

    def usage(self) -> EmbeddingUsage:
        return EmbeddingUsage(0, 0.0)


def make_assistant(cited_ids: list[str]) -> Assistant:
    rewriter = QueryRewriter(FixedChatModel({"official_query": "certified English translation"}, REWRITE_USAGE))
    retriever = RewritingRetriever(FixedRetriever(), rewriter, keep_original=True)
    answer_model = FixedChatModel({"answerable": True, "answer": "Yes.", "cited_chunk_ids": cited_ids}, ANSWER_USAGE)
    return Assistant(Answerer(retriever, answer_model), rewriter, FreeEmbedder())


def test_reply_cost_covers_this_question_only():
    assistant = make_assistant(["I-485-0009"])

    first = assistant.ask("Do I need a translation?")
    second = assistant.ask("Do I need a translation?")  # the rewrite is cached, so only the answer is paid

    assert first.cost_usd == pytest.approx(0.003)
    assert second.cost_usd == pytest.approx(0.002)
    assert first.search_query == "certified English translation"
    assert assistant.questions == 2
    assert assistant.total_cost_usd() == pytest.approx(0.005)


def test_reply_warns_about_citations_the_model_was_not_given():
    reply = make_assistant(["I-485-0009", "I-765-0001"]).ask("Do I need a translation?")

    assert reply.warnings() == [
        "The model cited passages it was not given: I-765-0001",
        "This answer is not backed by a valid source; check uscis.gov before relying on it.",
    ]


class StubAssistant:
    def __init__(self, error: Exception | None = None):
        self._error = error
        self.questions: list[str] = []

    def ask(self, question: str) -> Reply:
        self.questions.append(question)
        if self._error:
            raise self._error
        answer = Answer(question, True, "Yes, submit a full English translation.", (Citation.of(PASSAGE),), (),
                        ANSWER_USAGE, (PASSAGE,))
        return Reply(answer, "translation requirements", 0.0013)


def test_ask_returns_the_answer_with_sources():
    assistant = StubAssistant()
    client = TestClient(create_app(assistant))

    response = client.post("/api/ask", json={"question": "  Do I need a translation?  "})

    assert response.status_code == 200
    assert response.json() == {
        "answerable": True,
        "answer": "Yes, submit a full English translation.",
        "sources": [Citation.of(PASSAGE).label],
        "warnings": [],
        "cost_usd": 0.0013,
    }
    assert assistant.questions == ["Do I need a translation?"]


@pytest.mark.parametrize("question", ["", "   ", "x" * 1001])
def test_ask_rejects_blank_or_too_long_questions(question):
    assistant = StubAssistant()

    response = TestClient(create_app(assistant)).post("/api/ask", json={"question": question})

    assert response.status_code == 422
    assert assistant.questions == []


def test_ask_reports_a_failed_answer_without_leaking_details():
    error = APIConnectionError(request=None, message="connection to api.openai.com failed")  # type: ignore[arg-type]
    client = TestClient(create_app(StubAssistant(error)))

    response = client.post("/api/ask", json={"question": "Do I need a translation?"})

    assert response.status_code == 502
    assert "openai" not in response.text.lower()
