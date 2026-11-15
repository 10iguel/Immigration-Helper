"""Retrieval-augmented answering: find the passages, then answer only from them."""
from immigration_helper.answering.answer import Answer, Citation
from immigration_helper.answering.prompt import ANSWER_SCHEMA, build_messages
from immigration_helper.chat_model import ChatModel
from immigration_helper.retrieval import Retriever


class Answerer:
    def __init__(self, retriever: Retriever, chat_model: ChatModel, passages: int = 5):
        self._retriever = retriever
        self._chat_model = chat_model
        self._passages = passages

    def answer(self, question: str) -> Answer:
        passages = {result.chunk.id: result.chunk for result in self._retriever.search(question, self._passages)}
        result = self._chat_model.complete_json(
            build_messages(question, list(passages.values())), ANSWER_SCHEMA, schema_name="grounded_answer"
        )
        cited_ids = list(dict.fromkeys(result.content["cited_chunk_ids"]))  # dedupe, keep order
        return Answer(
            question=question,
            answerable=result.content["answerable"],
            text=result.content["answer"],
            citations=tuple(Citation.of(passages[chunk_id]) for chunk_id in cited_ids if chunk_id in passages),
            rejected_citation_ids=tuple(chunk_id for chunk_id in cited_ids if chunk_id not in passages),
            usage=result.usage,
            passages=tuple(passages.values()),
        )
