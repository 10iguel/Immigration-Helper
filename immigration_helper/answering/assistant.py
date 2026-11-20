"""The assistant behind every chat front end (terminal and web): one message in, a reply and its cost out."""
import threading
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from immigration_helper import config
from immigration_helper.answering.agent import Agent, InstructionSearch, PriorMessage
from immigration_helper.answering.answer import Answer
from immigration_helper.chat_model import NO_USAGE, OpenAIChatModel
from immigration_helper.ingestion import ChunkStore
from immigration_helper.retrieval import Embedder, EmbeddingRetriever, OpenAIEmbedder

DISCLAIMER = ("Answers come only from the official I-130, I-131, I-485 and I-765 instructions. This is not legal "
              "advice. Confirm important details on uscis.gov or with an immigration attorney.")


@dataclass(frozen=True)
class AssistantSettings:
    passages: int = config.ANSWER_PASSAGES  # per search
    form_filter: bool = config.FORM_FILTER
    chat_model: str = config.CHAT_MODEL
    embedding_model: str = config.EMBEDDING_MODEL
    chunks_path: Path = config.CHUNKS_PATH
    index_dir: Path = config.VECTOR_INDEX_DIR


@dataclass(frozen=True)
class Reply:
    answer: Answer
    cost_usd: float  # every model call and embedding for this message

    @property
    def search_query(self) -> str:
        """The agent's search queries, for logs and the database ("" when it didn't search)."""
        return " | ".join(self.answer.searches)

    def warnings(self) -> list[str]:
        """Reasons not to trust the answer, shown next to it."""
        warnings = []
        if self.answer.rejected_citation_ids:
            warnings.append("The model cited passages it was not given: "
                            + ", ".join(self.answer.rejected_citation_ids))
        if self.answer.answerable and not self.answer.is_grounded:
            warnings.append("This answer is not backed by a valid source; check uscis.gov before relying on it.")
        return warnings


class Assistant:
    """Answers one message at a time and keeps a running total of what the messages cost.

    Messages are answered one at a time (a lock), so each reply's cost is exact even when a web server
    handles several requests at once.
    """

    def __init__(self, agent: Agent, embedder: Embedder):
        self._agent = agent
        self._embedder = embedder
        self._answer_usage = NO_USAGE
        self._questions = 0
        self._lock = threading.Lock()

    @classmethod
    def build(cls, settings: AssistantSettings = AssistantSettings()) -> "Assistant":
        """The default OpenAI pipeline; reads the key from the OPENAI_API_KEY environment variable."""
        chunks = ChunkStore(settings.chunks_path).load()
        embedder = OpenAIEmbedder(settings.embedding_model)
        search = InstructionSearch(EmbeddingRetriever(chunks, embedder, settings.index_dir),
                                   known_forms={chunk.form for chunk in chunks},
                                   passages=settings.passages, form_filter=settings.form_filter)
        return cls(Agent(OpenAIChatModel(settings.chat_model), search), embedder)

    def ask(self, question: str, history: Sequence[PriorMessage] = ()) -> Reply:
        with self._lock:
            cost_before = self.total_cost_usd()
            answer = self._agent.reply(question, history)
            self._answer_usage += answer.usage
            self._questions += 1
            return Reply(answer, self.total_cost_usd() - cost_before)

    @property
    def questions(self) -> int:
        return self._questions

    def total_cost_usd(self) -> float:
        return self._answer_usage.cost_usd + self._embedder.usage().cost_usd
