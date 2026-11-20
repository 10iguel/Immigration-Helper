import json
from types import SimpleNamespace

import pytest

from immigration_helper.answering import Agent, Citation, InstructionSearch, PriorMessage, ReplyKind
from immigration_helper.answering.agent import HISTORY_MESSAGES, MAX_SEARCHES, UNGROUNDED_REPLY
from immigration_helper.answering.prompt import SEARCH_TOOL
from immigration_helper.chat_model import ChatUsage, OpenAIChatModel, ToolCall, ToolStep
from immigration_helper.models import FormId
from immigration_helper.retrieval import ScoredChunk
from tests.factories import make_chunk

TRANSLATIONS = make_chunk(
    "If you submit a document with information in a foreign language, you must also submit a full English translation.",
    form="I-485", chunk_id="I-485-0009", heading="General Instructions",
)
I765_TRANSLATIONS = make_chunk("Same translation rule.", form="I-765", chunk_id="I-765-0042", heading="General Instructions")
USAGE = ChatUsage(input_tokens=100, output_tokens=10, cost_usd=0.001)
QUESTION = "My birth certificate is in Spanish. Do I need to get it translated?"


class RecordingRetriever:
    name = "recording"

    def __init__(self, chunks=(TRANSLATIONS, I765_TRANSLATIONS)):
        self._chunks = chunks
        self.queries: list[str] = []

    def search(self, query: str, k: int) -> list[ScoredChunk]:
        self.queries.append(query)
        return [ScoredChunk(chunk, 1.0) for chunk in self._chunks][:k]


class ScriptedModel:
    """Plays back a fixed list of steps: tool calls (a search query) or a final reply."""

    model = "fake"

    def __init__(self, *steps):
        self._steps = list(steps)
        self.calls: list[tuple[list[dict], list]] = []

    def complete_with_tools(self, messages, tools, schema, schema_name) -> ToolStep:
        self.calls.append((list(messages), list(tools)))
        step = self._steps.pop(0)
        if isinstance(step, str):  # a search query
            call = ToolCall(f"call-{len(self.calls)}", SEARCH_TOOL.name, {"query": step})
            return ToolStep((call,), None, {"role": "assistant", "tool_calls": [call.call_id]}, USAGE)
        return ToolStep((), step, {"role": "assistant", "content": json.dumps(step)}, USAGE)


def reply(kind: str, text: str = "Yes.", cited: list[str] | None = None) -> dict:
    return {"reply_type": kind, "answer": text, "cited_chunk_ids": cited or []}


def make_agent(model, retriever=None, form_filter=True) -> tuple[Agent, RecordingRetriever]:
    retriever = retriever or RecordingRetriever()
    search = InstructionSearch(retriever, {FormId("I-485"), FormId("I-765")}, passages=8, form_filter=form_filter)
    return Agent(model, search), retriever


def test_agent_searches_then_answers_with_citations_from_chunk_metadata():
    model = ScriptedModel("certified English translation of foreign-language documents",
                          reply("answer", cited=["I-485-0009", "I-485-0009"]))
    agent, retriever = make_agent(model)

    answer = agent.reply(QUESTION)

    assert answer.kind is ReplyKind.ANSWER and answer.is_grounded
    assert answer.searches == ("certified English translation of foreign-language documents",)
    assert answer.citations == (
        Citation("I-485-0009", FormId("I-485"), "Form I-485 Instructions (08/21/25), p. 1: General Instructions"),
    )
    # The search used the person's words plus the agent's query (original + rewrite).
    assert retriever.queries == [f"{QUESTION}\ncertified English translation of foreign-language documents"]
    # The passages went back to the model as the tool result, and both model calls were paid for.
    assert "[I-485-0009]" in model.calls[1][0][-1]["content"]
    assert answer.usage.cost_usd == pytest.approx(0.002)


def test_small_talk_gets_a_conversation_reply_without_searching():
    model = ScriptedModel(reply("conversation", "You're welcome!"))
    agent, retriever = make_agent(model)

    answer = agent.reply("awesome, thanks!")

    assert answer.kind is ReplyKind.CONVERSATION
    assert not answer.answerable and answer.searches == () and answer.citations == ()
    assert retriever.queries == []


def test_follow_ups_see_the_recent_conversation():
    history = [PriorMessage("user", f"question {n}") if n % 2 == 0 else PriorMessage("assistant", f"answer {n}")
               for n in range(10)]
    model = ScriptedModel(reply("conversation", "Hi"))
    agent, _ = make_agent(model)

    agent.reply("What about my mom?", history)

    messages = model.calls[0][0]
    assert messages[0]["role"] == "system"
    assert [m["content"] for m in messages[1:-1]] == [prior.text for prior in history[-HISTORY_MESSAGES:]]
    assert messages[-1] == {"role": "user", "content": "What about my mom?"}


def test_citations_of_passages_it_was_not_given_are_rejected():
    model = ScriptedModel("translation", reply("answer", cited=["I-485-0009", "I-130-0001"]))
    agent, _ = make_agent(model)

    answer = agent.reply(QUESTION)

    assert answer.rejected_citation_ids == ("I-130-0001",)
    assert not answer.is_grounded
    assert answer.kind is ReplyKind.ANSWER  # one valid source, so it's shown, with a warning


def test_an_answer_with_no_valid_source_is_replaced_before_anyone_sees_it():
    # It answered from memory, without searching, and cited a passage it was never given.
    model = ScriptedModel(reply("answer", "File Form I-90 as soon as possible.", cited=["I-485-0009"]))
    agent, _ = make_agent(model)

    answer = agent.reply("My green card expires next month. How do I renew it?")

    assert answer.kind is ReplyKind.NOT_COVERED
    assert answer.text == UNGROUNDED_REPLY
    assert answer.withheld_text == "File Form I-90 as soon as possible."
    assert answer.rejected_citation_ids == ("I-485-0009",)


def test_the_search_limit_forces_a_reply():
    model = ScriptedModel("first query", "second query", reply("not_covered", "The instructions don't cover this."))
    agent, _ = make_agent(model)

    answer = agent.reply(QUESTION)

    assert len(answer.searches) == MAX_SEARCHES == 2
    assert [len(tools) for _, tools in model.calls] == [1, 1, 0]  # no search tool on the last call
    assert answer.kind is ReplyKind.NOT_COVERED


def test_the_form_filter_only_looks_at_the_persons_words():
    # The agent's query names Form I-765, but the person asked about Form I-485.
    model = ScriptedModel("translation rule, Form I-765", reply("answer", cited=["I-485-0009"]))
    agent, _ = make_agent(model)

    answer = agent.reply("Do I need a translation for my Form I-485?")

    assert [chunk.form.value for chunk in answer.passages] == ["I-485"]


def fake_openai_client(message: SimpleNamespace, finish_reason: str = "stop") -> SimpleNamespace:
    completion = SimpleNamespace(
        choices=[SimpleNamespace(message=message, finish_reason=finish_reason)],
        usage=SimpleNamespace(prompt_tokens=1_000_000, completion_tokens=500_000),
    )
    requests: list[dict] = []

    def create(**request):
        requests.append(request)
        return completion

    return SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)), requests=requests)


def openai_message(content=None, refusal=None, tool_calls=None) -> SimpleNamespace:
    return SimpleNamespace(content=content, refusal=refusal, tool_calls=tool_calls)


def test_openai_chat_model_parses_json_and_prices_tokens():
    content = reply("answer")
    client = fake_openai_client(openai_message(json.dumps(content)))

    result = OpenAIChatModel("gpt-4.1-mini", client).complete_json([], {}, "clearpath_reply")

    assert result.content == content
    assert result.usage.cost_usd == pytest.approx(0.40 + 0.80)
    assert "tools" not in client.requests[0]


def test_openai_chat_model_returns_tool_calls_and_sends_tool_definitions():
    call = SimpleNamespace(id="call-1", function=SimpleNamespace(name="search_instructions",
                                                                 arguments='{"query": "translation"}'))
    client = fake_openai_client(openai_message(tool_calls=[call]), finish_reason="tool_calls")

    step = OpenAIChatModel("gpt-4.1-mini", client).complete_with_tools([], [SEARCH_TOOL], {}, "clearpath_reply")

    assert step.tool_calls == (ToolCall("call-1", "search_instructions", {"query": "translation"}),)
    assert step.message["tool_calls"][0]["function"]["arguments"] == '{"query": "translation"}'
    assert step.tool_calls[0].result_message("passages") == {"role": "tool", "tool_call_id": "call-1",
                                                             "content": "passages"}
    request = client.requests[0]
    assert request["tools"][0]["function"]["name"] == "search_instructions"
    assert request["tools"][0]["function"]["strict"] is True
    assert request["parallel_tool_calls"] is False


def test_openai_chat_model_raises_on_refusal():
    client = fake_openai_client(openai_message(refusal="I can't help with that."))

    with pytest.raises(RuntimeError, match="refused"):
        OpenAIChatModel("gpt-4.1-mini", client).complete_json([], {}, "clearpath_reply")


def test_openai_chat_model_raises_on_truncated_reply():
    client = fake_openai_client(openai_message('{"reply_type": "ans'), finish_reason="length")

    with pytest.raises(RuntimeError, match="stopped early"):
        OpenAIChatModel("gpt-4.1-mini", client).complete_json([], {}, "clearpath_reply")


def test_unknown_chat_model_is_rejected():
    with pytest.raises(ValueError):
        OpenAIChatModel("gpt-unknown", client=SimpleNamespace())
