"""The tool-calling agent: the model decides whether to search the instructions, writes the query itself (using the
conversation so far), and then replies from the passages it found."""
from collections.abc import Sequence
from dataclasses import dataclass

from immigration_helper.answering.answer import Answer, Citation, ReplyKind
from immigration_helper.answering.prompt import AGENT_PROMPT, REPLY_SCHEMA, SEARCH_TOOL, format_passages
from immigration_helper.chat_model import NO_USAGE, ToolCall, ToolChatModel
from immigration_helper.models import Chunk, FormId
from immigration_helper.retrieval import FormFilterRetriever, Retriever

MAX_SEARCHES = 2  # per message; after that the model must reply with what it has
UNGROUNDED_REPLY = ("I couldn't find this in the official instructions for Forms I-130, I-131, I-485 and I-765, so I "
                    "won't guess. Please check uscis.gov or ask an immigration attorney.")
HISTORY_MESSAGES = 6  # earlier messages sent along (3 questions and answers), enough for follow-ups


@dataclass(frozen=True)
class PriorMessage:
    """An earlier message in the conversation, as context for follow-up questions."""
    role: str  # "user" or "assistant"
    text: str


class InstructionSearch:
    """The search tool. It searches with the person's message plus the agent's query, the best setup in the
    retrieval evaluation (original question + rewrite), and the form filter only looks at the person's own words."""

    def __init__(self, base: Retriever, known_forms: set[FormId], passages: int, form_filter: bool = True):
        self._base = base
        self._filter = FormFilterRetriever(base, known_forms) if form_filter else None
        self._passages = passages

    def search(self, user_message: str, query: str) -> list[Chunk]:
        text = f"{user_message}\n{query}"
        if self._filter:
            results = self._filter.search_named(text, self._passages, named_by=user_message)
        else:
            results = self._base.search(text, self._passages)
        return [result.chunk for result in results]


class Agent:
    def __init__(self, chat_model: ToolChatModel, search: InstructionSearch):
        self._chat_model = chat_model
        self._search = search

    def reply(self, message: str, history: Sequence[PriorMessage] = ()) -> Answer:
        messages = [
            {"role": "system", "content": AGENT_PROMPT},
            *({"role": prior.role, "content": prior.text} for prior in history[-HISTORY_MESSAGES:]),
            {"role": "user", "content": message},
        ]
        passages: dict[str, Chunk] = {}
        searches: list[str] = []
        usage = NO_USAGE
        while True:
            tools = [SEARCH_TOOL] if len(searches) < MAX_SEARCHES else []
            step = self._chat_model.complete_with_tools(messages, tools, REPLY_SCHEMA, schema_name="clearpath_reply")
            usage += step.usage
            if not step.tool_calls:
                return _answer(message, step.content, passages, tuple(searches), usage)
            messages.append(step.message)
            for call in step.tool_calls:
                found = self._run(call, message)
                searches.append(call.arguments["query"])
                passages.update((chunk.id, chunk) for chunk in found)
                messages.append(call.result_message(format_passages(found) or "No passages found."))

    def _run(self, call: ToolCall, message: str) -> list[Chunk]:
        if call.name != SEARCH_TOOL.name:
            raise RuntimeError(f"The model called an unknown tool: {call.name!r}")
        return self._search.search(message, call.arguments["query"])


def _answer(message: str, content: dict, passages: dict[str, Chunk], searches: tuple[str, ...], usage) -> Answer:
    """Grounding is enforced in code, not only asked for in the prompt: only passages from this message's searches
    count as sources, their labels come from the chunk metadata (never from the model's text), and an answer with no
    valid source is replaced by a safe reply instead of being shown."""
    cited_ids = list(dict.fromkeys(content["cited_chunk_ids"]))  # dedupe, keep order
    kind, text, withheld = ReplyKind(content["reply_type"]), content["answer"], None
    citations = tuple(Citation.of(passages[chunk_id]) for chunk_id in cited_ids if chunk_id in passages)
    if kind is ReplyKind.ANSWER and not citations:
        kind, text, withheld = ReplyKind.NOT_COVERED, UNGROUNDED_REPLY, text
    return Answer(
        question=message,
        kind=kind,
        text=text,
        citations=citations,
        rejected_citation_ids=tuple(chunk_id for chunk_id in cited_ids if chunk_id not in passages),
        usage=usage,
        passages=tuple(passages.values()),
        searches=searches,
        withheld_text=withheld,
    )
