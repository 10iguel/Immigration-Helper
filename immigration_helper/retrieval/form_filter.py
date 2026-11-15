"""Form filter: when a query names a loaded form, search only that form's passages.

All four instructions repeat some rules word for word (e.g. "Translations"), so a question about Form I-485 can
otherwise retrieve the identical I-765 passage and cite the wrong form. Form numbers follow a fixed pattern, so
plain code detects them exactly; no LLM is needed.
"""
import re

from immigration_helper.models import FormId
from immigration_helper.retrieval.retriever import Retriever, ScoredChunk

_FORM_PATTERN = re.compile(r"\bI-\d{3}[A-Z]?\b", re.IGNORECASE)


class FormFilterRetriever:
    """Wraps any retriever. Fetches extra candidates and keeps those from the named forms.

    Filtering after retrieval is simple at this scale (hundreds of chunks); with a much larger corpus the filter
    belongs in the vector store's metadata query instead.
    """

    def __init__(self, base: Retriever, known_forms: set[FormId], candidates: int = 200):
        self._base = base
        self._known_forms = known_forms
        self._candidates = candidates
        self.name = f"{base.name}+formfilter"

    def forms_named_in(self, query: str) -> set[FormId]:
        named = {FormId(match.upper()) for match in _FORM_PATTERN.findall(query)}
        return named & self._known_forms  # forms we don't have (e.g. I-864) would filter out everything

    def search(self, query: str, k: int) -> list[ScoredChunk]:
        forms = self.forms_named_in(query)
        if not forms:
            return self._base.search(query, k)
        results = self._base.search(query, max(k, self._candidates))
        return [result for result in results if result.chunk.form in forms][:k]
