import pytest
from fastapi.testclient import TestClient
from openai import APIConnectionError

from immigration_helper.accounts import AccountService
from immigration_helper.answering import Agent, Citation, InstructionSearch
from immigration_helper.answering.assistant import Assistant
from immigration_helper.api import SESSION_COOKIE, create_app
from immigration_helper.history import ChatService
from immigration_helper.models import FormId
from immigration_helper.retrieval import EmbeddingUsage
from tests.fakes import PASSAGE, InMemoryConversationStore, InMemoryUserStore, StubAssistant
from tests.test_answering import RecordingRetriever, ScriptedModel, reply


class FreeEmbedder:
    model = "fake"

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [[1.0] for _ in texts]

    def usage(self) -> EmbeddingUsage:
        return EmbeddingUsage(0, 0.0)


def make_assistant(*steps) -> Assistant:
    search = InstructionSearch(RecordingRetriever((PASSAGE,)), {FormId("I-485")}, passages=8)
    return Assistant(Agent(ScriptedModel(*steps), search), FreeEmbedder())


def test_reply_cost_covers_this_message_only():
    assistant = make_assistant("certified English translation", reply("answer", cited=["I-485-0009"]),
                               reply("conversation", "You're welcome!"))

    first = assistant.ask("Do I need a translation?")  # a search and an answer: two model calls
    second = assistant.ask("thanks!")  # no search: one model call

    assert first.cost_usd == pytest.approx(0.002)
    assert second.cost_usd == pytest.approx(0.001)
    assert first.search_query == "certified English translation"
    assert second.search_query == ""
    assert assistant.questions == 2
    assert assistant.total_cost_usd() == pytest.approx(0.003)


def test_reply_warns_about_citations_the_model_was_not_given():
    answer = make_assistant("translation", reply("answer", cited=["I-485-0009", "I-765-0001"])).ask("Translation?")

    assert answer.warnings() == [
        "The model cited passages it was not given: I-765-0001",
        "This answer is not backed by a valid source; check uscis.gov before relying on it.",
    ]


CREDENTIALS = {"email": "ana@example.com", "password": "correct horse battery"}


def make_client(assistant: StubAssistant | None = None) -> TestClient:
    chats = ChatService(assistant or StubAssistant(), InMemoryConversationStore())
    return TestClient(create_app(AccountService(InMemoryUserStore()), chats))


def signed_up_client(assistant: StubAssistant | None = None) -> TestClient:
    client = make_client(assistant)
    assert client.post("/api/auth/signup", json=CREDENTIALS).status_code == 201
    return client


def test_sign_up_sets_an_http_only_cookie_and_logs_the_user_in():
    client = make_client()

    response = client.post("/api/auth/signup", json=CREDENTIALS)

    assert response.json() == {"email": "ana@example.com"}
    assert "httponly" in response.headers["set-cookie"].lower()
    assert client.get("/api/auth/me").json() == {"email": "ana@example.com"}


def test_wrong_password_and_duplicate_sign_up_are_rejected():
    client = signed_up_client()
    client.cookies.clear()

    assert client.post("/api/auth/login", json={**CREDENTIALS, "password": "wrong password"}).status_code == 401
    assert client.post("/api/auth/signup", json=CREDENTIALS).status_code == 409
    assert client.post("/api/auth/signup", json={"email": "bo@example.com", "password": "short"}).status_code == 422
    assert client.post("/api/auth/login", json=CREDENTIALS).status_code == 200


def test_logging_out_ends_the_session():
    client = signed_up_client()
    token = client.cookies[SESSION_COOKIE]

    assert client.post("/api/auth/logout").status_code == 204
    client.cookies.set(SESSION_COOKIE, token)  # even a copied token stops working
    assert client.get("/api/auth/me").status_code == 401


def test_asking_requires_login():
    assistant = StubAssistant()

    response = make_client(assistant).post("/api/ask", json={"question": "Do I need a translation?"})

    assert response.status_code == 401
    assert assistant.questions == []


def test_ask_saves_the_exchange_and_the_conversation_can_be_reopened():
    client = signed_up_client()

    first = client.post("/api/ask", json={"question": "  Do I need a translation?  "}).json()
    client.post("/api/ask", json={"question": "Who can translate it?", "conversation_id": first["conversation_id"]})

    assert first["answer"] == "Yes, submit a full English translation."
    assert first["sources"] == [Citation.of(PASSAGE).label]
    assert [c["title"] for c in client.get("/api/conversations").json()] == ["Do I need a translation?"]
    conversation = client.get(f"/api/conversations/{first['conversation_id']}").json()
    answer = "Yes, submit a full English translation."
    assert [(m["role"], m["content"]) for m in conversation["messages"]] == [
        ("user", "Do I need a translation?"),
        ("assistant", answer),
        ("user", "Who can translate it?"),
        ("assistant", answer),
    ]
    assert conversation["messages"][1]["sources"] == [Citation.of(PASSAGE).label]
    assert conversation["messages"][0]["cost_usd"] is None


def test_another_users_conversation_is_not_found():
    client = signed_up_client()
    anas = client.post("/api/ask", json={"question": "Do I need a translation?"}).json()["conversation_id"]
    client.cookies.clear()
    client.post("/api/auth/signup", json={"email": "bo@example.com", "password": "another password"})

    assert client.get(f"/api/conversations/{anas}").status_code == 404
    assert client.post("/api/ask", json={"question": "Hi", "conversation_id": anas}).status_code == 404
    assert client.get("/api/conversations").json() == []


@pytest.mark.parametrize("question", ["", "   ", "x" * 1001])
def test_ask_rejects_blank_or_too_long_questions(question):
    assistant = StubAssistant()

    response = signed_up_client(assistant).post("/api/ask", json={"question": question})

    assert response.status_code == 422
    assert assistant.questions == []


def test_ask_reports_a_failed_answer_without_leaking_details():
    error = APIConnectionError(request=None, message="connection to api.openai.com failed")  # type: ignore[arg-type]

    response = signed_up_client(StubAssistant(error)).post("/api/ask", json={"question": "Do I need a translation?"})

    assert response.status_code == 502
    assert "openai" not in response.text.lower()
