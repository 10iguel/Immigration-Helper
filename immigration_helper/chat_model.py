"""Calls a chat model for JSON that follows a schema, optionally letting it call tools first, and measures what
each call costs. All OpenAI request and message formats live here."""
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


@dataclass(frozen=True)
class ToolSpec:
    """A function the model may call: a name, what it does, and a JSON schema for its arguments."""
    name: str
    description: str
    parameters: dict


@dataclass(frozen=True)
class ToolCall:
    call_id: str
    name: str
    arguments: dict

    def result_message(self, content: str) -> dict:
        """The message that gives the tool's result back to the model."""
        return {"role": "tool", "tool_call_id": self.call_id, "content": content}


@dataclass(frozen=True)
class ToolStep:
    """One model turn: either tool calls to run (then call the model again), or the final JSON reply."""
    tool_calls: tuple[ToolCall, ...]
    content: dict | None  # the final reply, when there are no tool calls
    message: dict  # the model's message, to append to the conversation before the tool results
    usage: ChatUsage


class ChatModel(Protocol):
    model: str

    def complete_json(self, messages: list[dict], schema: dict, schema_name: str) -> ChatResult: ...


class ToolChatModel(ChatModel, Protocol):
    def complete_with_tools(self, messages: list[dict], tools: list[ToolSpec], schema: dict,
                            schema_name: str) -> ToolStep: ...


class OpenAIChatModel:
    """Uses strict structured outputs, so the reply always parses into the given JSON schema."""

    def __init__(self, model: str, client: OpenAI | None = None):
        if model not in _USD_PER_MILLION_TOKENS:
            raise ValueError(f"No price known for chat model {model!r}")
        self.model = model
        self._client = client or OpenAI()

    def complete_json(self, messages: list[dict], schema: dict, schema_name: str) -> ChatResult:
        step = self.complete_with_tools(messages, [], schema, schema_name)
        return ChatResult(step.content, step.usage)

    def complete_with_tools(self, messages: list[dict], tools: list[ToolSpec], schema: dict,
                            schema_name: str) -> ToolStep:
        request = {
            "model": self.model,
            "messages": messages,
            "temperature": 0,
            "max_completion_tokens": _MAX_OUTPUT_TOKENS,
            "response_format": {"type": "json_schema",
                                "json_schema": {"name": schema_name, "schema": schema, "strict": True}},
        }
        if tools:
            # One call at a time: strict argument schemas aren't guaranteed for parallel calls.
            request["tools"] = [_tool_definition(tool) for tool in tools]
            request["parallel_tool_calls"] = False
        completion = self._client.chat.completions.create(**request)
        choice, usage = completion.choices[0], self._usage(completion.usage)

        if choice.message.tool_calls:
            calls = tuple(ToolCall(call.id, call.function.name, json.loads(call.function.arguments))
                          for call in choice.message.tool_calls)
            message = {"role": "assistant", "content": choice.message.content, "tool_calls": [
                {"id": call.id, "type": "function",
                 "function": {"name": call.function.name, "arguments": call.function.arguments}}
                for call in choice.message.tool_calls
            ]}
            return ToolStep(calls, None, message, usage)

        if choice.message.refusal:
            raise RuntimeError(f"{self.model} refused to answer: {choice.message.refusal}")
        if choice.finish_reason != "stop":
            raise RuntimeError(f"{self.model} stopped early ({choice.finish_reason}); the JSON reply is incomplete")
        content = choice.message.content
        return ToolStep((), json.loads(content), {"role": "assistant", "content": content}, usage)

    def _usage(self, usage) -> ChatUsage:
        input_price, output_price = _USD_PER_MILLION_TOKENS[self.model]
        cost = (usage.prompt_tokens * input_price + usage.completion_tokens * output_price) / 1_000_000
        return ChatUsage(usage.prompt_tokens, usage.completion_tokens, cost)


def _tool_definition(tool: ToolSpec) -> dict:
    return {"type": "function", "function": {
        "name": tool.name, "description": tool.description, "parameters": tool.parameters, "strict": True,
    }}
