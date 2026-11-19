"""HTTP API for the web chat page. It only translates between JSON and the Assistant."""
import logging
from typing import Protocol

from fastapi import FastAPI, HTTPException
from openai import OpenAIError
from pydantic import BaseModel, Field, field_validator

from immigration_helper.answering.assistant import Reply

_MAX_QUESTION_CHARS = 1000
logger = logging.getLogger(__name__)


class QuestionAnswerer(Protocol):
    def ask(self, question: str) -> Reply: ...


class AskRequest(BaseModel):
    question: str = Field(min_length=1, max_length=_MAX_QUESTION_CHARS)

    @field_validator("question")
    @classmethod
    def _not_blank(cls, question: str) -> str:
        if not question.strip():
            raise ValueError("question must not be blank")
        return question.strip()


class AskResponse(BaseModel):
    answerable: bool
    answer: str
    sources: list[str]
    warnings: list[str]
    cost_usd: float

    @classmethod
    def of(cls, reply: Reply) -> "AskResponse":
        return cls(
            answerable=reply.answer.answerable,
            answer=reply.answer.text,
            sources=[citation.label for citation in reply.answer.citations],
            warnings=reply.warnings(),
            cost_usd=reply.cost_usd,
        )


def create_app(assistant: QuestionAnswerer) -> FastAPI:
    app = FastAPI(title="USCIS Form Helper API")

    @app.post("/api/ask")
    def ask(request: AskRequest) -> AskResponse:
        # A plain (non-async) handler: FastAPI runs it in a worker thread, so a slow answer doesn't block the server.
        try:
            return AskResponse.of(assistant.ask(request.question))
        except (OpenAIError, RuntimeError):
            logger.exception("Answering failed for a question")
            raise HTTPException(status_code=502, detail="The assistant could not answer right now. Please try again.")

    return app
