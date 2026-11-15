from immigration_helper.chat_model import ChatResult, ChatUsage
from immigration_helper.retrieval import QueryRewriter, RewritingRetriever, ScoredChunk
from tests.factories import make_chunk

USAGE = ChatUsage(input_tokens=100, output_tokens=20, cost_usd=0.001)


class FakeChatModel:
    model = "fake"

    def __init__(self, official_query: str):
        self._official_query = official_query
        self.calls = 0
        self.last_messages: list[dict] = []

    def complete_json(self, messages: list[dict], schema: dict, schema_name: str) -> ChatResult:
        self.calls += 1
        self.last_messages = messages
        return ChatResult({"official_query": self._official_query}, USAGE)


class RecordingRetriever:
    name = "recording"

    def __init__(self):
        self.queries: list[str] = []

    def search(self, query: str, k: int) -> list[ScoredChunk]:
        self.queries.append(query)
        return [ScoredChunk(make_chunk("Adjustment of status."), 1.0)]


def test_rewriter_sends_question_and_returns_official_query():
    model = FakeChatModel("adjustment of status, Form I-485")

    rewritten = QueryRewriter(model).rewrite("Can I work while my green card is pending?")

    assert rewritten == "adjustment of status, Form I-485"
    assert model.last_messages[-1]["content"] == "Question: Can I work while my green card is pending?"


def test_rewriter_calls_the_model_once_per_distinct_question_and_sums_usage():
    model = FakeChatModel("adjustment of status")
    rewriter = QueryRewriter(model)

    rewriter.rewrite("green card?")
    rewriter.rewrite("green card?")
    rewriter.rewrite("work permit?")

    assert model.calls == 2
    assert rewriter.usage() == ChatUsage(200, 40, 0.002)
    assert rewriter.rewrites() == {"green card?": "adjustment of status", "work permit?": "adjustment of status"}


def test_rewriting_retriever_searches_with_rewritten_query():
    base = RecordingRetriever()
    retriever = RewritingRetriever(base, QueryRewriter(FakeChatModel("adjustment of status")))

    retriever.search("green card?", k=5)

    assert base.queries == ["adjustment of status"]
    assert retriever.name == "recording+rewrite"


def test_rewriting_retriever_can_keep_the_original_question():
    base = RecordingRetriever()
    retriever = RewritingRetriever(base, QueryRewriter(FakeChatModel("adjustment of status")), keep_original=True)

    retriever.search("green card?", k=5)

    assert base.queries == ["green card?\nadjustment of status"]
    assert retriever.name == "recording+rewrite+original"
