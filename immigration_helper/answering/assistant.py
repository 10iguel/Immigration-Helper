"""The assistant behind every chat front end (terminal and web): one question in, an answer and its cost out."""
import threading
from dataclasses import dataclass
from pathlib import Path

from immigration_helper import config
from immigration_helper.answering.answer import Answer
from immigration_helper.answering.answerer import Answerer
from immigration_helper.answering.pipeline import build_retriever
from immigration_helper.chat_model import NO_USAGE, OpenAIChatModel
from immigration_helper.ingestion import ChunkStore
from immigration_helper.retrieval import Embedder, OpenAIEmbedder, QueryRewriter

DISCLAIMER = ("Answers come only from the official I-130, I-131, I-485 and I-765 instructions. This is not legal "
              "advice. Confirm important details on uscis.gov or with an immigration attorney.")


@dataclass(frozen=True)
class AssistantSettings:
    passages: int = config.ANSWER_PASSAGES
    form_filter: bool = config.FORM_FILTER
    chat_model: str = config.CHAT_MODEL
    chunks_path: Path = config.CHUNKS_PATH
    index_dir: Path = config.VECTOR_INDEX_DIR


@dataclass(frozen=True)
class Reply:
    answer: Answer
    search_query: str
    cost_usd: float  # rewrite + search + answer for this question

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
    """Answers one question at a time and keeps a running total of what the questions cost.

    Questions are answered one at a time (a lock), so each reply's cost is exact even when a web server
    handles several requests at once.
    """

    def __init__(self, answerer: Answerer, rewriter: QueryRewriter, embedder: Embedder):
        self._answerer = answerer
        self._rewriter = rewriter
        self._embedder = embedder
        self._answer_usage = NO_USAGE
        self._questions = 0
        self._lock = threading.Lock()

    @classmethod
    def build(cls, settings: AssistantSettings = AssistantSettings()) -> "Assistant":
        """The default OpenAI pipeline; reads the key from the OPENAI_API_KEY environment variable."""
        chat_model = OpenAIChatModel(settings.chat_model)
        embedder = OpenAIEmbedder(config.EMBEDDING_MODEL)
        rewriter = QueryRewriter(chat_model)
        retriever = build_retriever(ChunkStore(settings.chunks_path).load(), embedder, rewriter,
                                    settings.index_dir, settings.form_filter)
        return cls(Answerer(retriever, chat_model, settings.passages), rewriter, embedder)

    def ask(self, question: str) -> Reply:
        with self._lock:
            cost_before = self.total_cost_usd()
            answer = self._answerer.answer(question)
            self._answer_usage += answer.usage
            self._questions += 1
            return Reply(answer, self._rewriter.rewrite(question), self.total_cost_usd() - cost_before)

    @property
    def questions(self) -> int:
        return self._questions

    def total_cost_usd(self) -> float:
        return self._answer_usage.cost_usd + self._rewriter.usage().cost_usd + self._embedder.usage().cost_usd
