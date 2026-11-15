"""Query rewriting: translate everyday wording into the vocabulary of the official instructions before searching.

Applicants say "green card" and "work permit"; the instructions say "lawful permanent resident" and
"Employment Authorization Document". Embeddings only partly bridge that gap, so an LLM rewrites the question first.
"""
from immigration_helper.chat_model import NO_USAGE, ChatModel, ChatUsage
from immigration_helper.retrieval.retriever import Retriever, ScoredChunk

# The examples use forms outside the loaded instructions (I-90, I-129F) so they don't leak evaluation answers.
REWRITE_PROMPT = """\
You turn a person's question about U.S. immigration paperwork into a search query for the official USCIS \
form instructions (Forms I-130, I-131, I-485 and I-765).

The instructions use formal vocabulary, so people's everyday words often don't appear in them. Rewrite the \
question with the terms the instructions would use: the official names of documents, statuses, processes and \
forms, and form numbers or eligibility categories when you are confident of them. Keep every detail of the \
person's situation. Do not answer the question, and do not add facts about the person that they didn't state.

Examples:
Question: I lost my green card. How do I replace it?
Query: replace lost Permanent Resident Card (Form I-551) of a lawful permanent resident, Form I-90 Application \
to Replace Permanent Resident Card

Question: Can my boyfriend from abroad come here so we can get married?
Query: U.S. citizen petitioner, petition for alien fiancé(e), K-1 nonimmigrant fiancé(e) visa, Form I-129F"""

REWRITE_SCHEMA = {
    "type": "object",
    "properties": {"official_query": {"type": "string", "description": "The question in official USCIS terms."}},
    "required": ["official_query"],
    "additionalProperties": False,
}


class QueryRewriter:
    """Rewrites each distinct question once and remembers it, so repeated searches cost nothing extra."""

    def __init__(self, chat_model: ChatModel):
        self._chat_model = chat_model
        self._rewrites: dict[str, str] = {}
        self._usage = NO_USAGE

    def rewrite(self, question: str) -> str:
        if question not in self._rewrites:
            messages = [
                {"role": "system", "content": REWRITE_PROMPT},
                {"role": "user", "content": f"Question: {question}"},
            ]
            result = self._chat_model.complete_json(messages, REWRITE_SCHEMA, schema_name="official_query")
            self._rewrites[question] = result.content["official_query"]
            self._usage += result.usage
        return self._rewrites[question]

    def rewrites(self) -> dict[str, str]:
        return dict(self._rewrites)

    def usage(self) -> ChatUsage:
        return self._usage


class RewritingRetriever:
    """Wraps any retriever and searches with the rewritten question, optionally keeping the original words too."""

    def __init__(self, base: Retriever, rewriter: QueryRewriter, keep_original: bool = False):
        self._base = base
        self._rewriter = rewriter
        self._keep_original = keep_original
        self.name = f"{base.name}+rewrite" + ("+original" if keep_original else "")

    def search(self, query: str, k: int) -> list[ScoredChunk]:
        official = self._rewriter.rewrite(query)
        return self._base.search(f"{query}\n{official}" if self._keep_original else official, k)
