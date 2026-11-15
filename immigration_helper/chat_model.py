"""Calls a chat model for JSON that follows a schema, and measures what each call costs."""
import json
from dataclasses import dataclass
from typing import Protocol

from openai import OpenAI

# USD per 1M tokens as (input, output), from the OpenAI pricing page; update if prices change.
_USD_PER_MILLION_TOKENS = {
    "gpt-4.1-mini": (0.40, 1.60),
    "gpt-4.1": (2.00, 8.00),
}
_MAX_OUTPUT_TOKENS = 800


@dataclass(frozen=True)
class ChatUsage:
    input_tokens: int
    output_tokens: int
    cost_usd: float

    def __add__(self, other: "ChatUsage") -> "ChatUsage":
        return ChatUsage(
            self.input_tokens + other.input_tokens,
            self.output_tokens + other.output_tokens,
            self.cost_usd + other.cost_usd,
        )


NO_USAGE = ChatUsage(0, 0, 0.0)


@dataclass(frozen=True)
class ChatResult:
    content: dict
    usage: ChatUsage


class ChatModel(Protocol):
    model: str

    def complete_json(self, messages: list[dict], schema: dict, schema_name: str) -> ChatResult: ...


class OpenAIChatModel:
    """Uses strict structured outputs, so the reply always parses into the given JSON schema."""

    def __init__(self, model: str, client: OpenAI | None = None):
        if model not in _USD_PER_MILLION_TOKENS:
            raise ValueError(f"No price known for chat model {model!r}")
        self.model = model
        self._client = client or OpenAI()

    def complete_json(self, messages: list[dict], schema: dict, schema_name: str) -> ChatResult:
        completion = self._client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=0,
            max_completion_tokens=_MAX_OUTPUT_TOKENS,
            response_format={"type": "json_schema", "json_schema": {"name": schema_name, "schema": schema, "strict": True}},
        )
        choice = completion.choices[0]
        if choice.message.refusal:
            raise RuntimeError(f"{self.model} refused to answer: {choice.message.refusal}")
        if choice.finish_reason != "stop":
            raise RuntimeError(f"{self.model} stopped early ({choice.finish_reason}); the JSON reply is incomplete")
        return ChatResult(json.loads(choice.message.content), self._usage(completion.usage))

    def _usage(self, usage) -> ChatUsage:
        input_price, output_price = _USD_PER_MILLION_TOKENS[self.model]
        cost = (usage.prompt_tokens * input_price + usage.completion_tokens * output_price) / 1_000_000
        return ChatUsage(usage.prompt_tokens, usage.completion_tokens, cost)
