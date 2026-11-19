"""Ask questions about the USCIS form instructions, from the project root:

    python -m immigration_helper.answering                                   # chat: ask one question after another
    python -m immigration_helper.answering "Can I travel while my I-485 is pending?"   # answer one question
"""
import argparse
from pathlib import Path

from openai import OpenAIError

from immigration_helper import config
from immigration_helper.answering.assistant import DISCLAIMER, Assistant, AssistantSettings, Reply

_QUIT_WORDS = {"quit", "exit", "q"}


def main() -> None:
    parser = argparse.ArgumentParser(description="Answer questions from the USCIS form instructions.")
    parser.add_argument("question", nargs="?", help="a single question; leave out to start a chat")
    parser.add_argument("--passages", type=int, default=config.ANSWER_PASSAGES, help="passages shown to the model")
    parser.add_argument("--form-filter", action=argparse.BooleanOptionalAction, default=config.FORM_FILTER,
                        help="search only forms named in the question")
    parser.add_argument("--model", default=config.CHAT_MODEL)
    parser.add_argument("--chunks", type=Path, default=config.CHUNKS_PATH)
    parser.add_argument("--index-dir", type=Path, default=config.VECTOR_INDEX_DIR)
    parser.add_argument("--show-rewrite", action="store_true", help="print the search query used")
    args = parser.parse_args()

    assistant = Assistant.build(AssistantSettings(args.passages, args.form_filter, args.model, args.chunks,
                                                  args.index_dir))
    session = _Session(assistant, args.show_rewrite)
    if args.question:
        session.ask(args.question)
    else:
        session.chat()


class _Session:
    """The terminal front end: reads questions and prints replies."""

    def __init__(self, assistant: Assistant, show_rewrite: bool):
        self._assistant = assistant
        self._show_rewrite = show_rewrite

    def chat(self) -> None:
        print(f"USCIS Form Helper: {DISCLAIMER}\nEach question is answered on its own, so include the details "
              "you need.\nType 'quit' to stop.\n")
        while True:
            try:
                question = input("Your question: ").strip()
            except (EOFError, KeyboardInterrupt):
                print()
                break
            if question.lower() in _QUIT_WORDS:
                break
            if not question:
                continue
            try:
                self.ask(question)
            except (OpenAIError, RuntimeError) as error:
                print(f"\nSorry, that question failed: {error}\nYou can try again or ask something else.")
            print("\n" + "-" * 80 + "\n")
        print(f"Session: {self._assistant.questions} questions, ${self._assistant.total_cost_usd():.6f} in total.")

    def ask(self, question: str) -> None:
        reply = self._assistant.ask(question)
        print()
        if self._show_rewrite:
            print(f"Search query: {reply.search_query}\n")
        print_reply(reply)
        print(f"\n[this answer: ${reply.cost_usd:.6f}; session total ${self._assistant.total_cost_usd():.6f}]")


def print_reply(reply: Reply) -> None:
    print(reply.answer.text)
    if reply.answer.citations:
        print("\nSources:")
        for citation in reply.answer.citations:
            print(f"  - {citation.label}")
    for warning in reply.warnings():
        print(f"\nWARNING: {warning}")


if __name__ == "__main__":
    main()
