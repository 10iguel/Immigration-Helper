from immigration_helper.models import FormId
from immigration_helper.retrieval import FormFilterRetriever, ScoredChunk
from tests.factories import make_chunk

RESULTS = [
    ScoredChunk(make_chunk("Translations.", form="I-765", chunk_id="I-765-0090"), 0.9),
    ScoredChunk(make_chunk("Translations.", form="I-131", chunk_id="I-131-0061"), 0.8),
    ScoredChunk(make_chunk("Translations.", form="I-485", chunk_id="I-485-0009"), 0.7),
    ScoredChunk(make_chunk("Birth certificate.", form="I-485", chunk_id="I-485-0021"), 0.6),
]
KNOWN_FORMS = {FormId(form) for form in ("I-130", "I-131", "I-485", "I-765")}


class FixedRetriever:
    name = "fixed"

    def __init__(self):
        self.requested_k: list[int] = []

    def search(self, query: str, k: int) -> list[ScoredChunk]:
        self.requested_k.append(k)
        return RESULTS[:k]


def ids(results: list[ScoredChunk]) -> list[str]:
    return [result.chunk.id for result in results]


def test_query_naming_a_form_keeps_only_that_forms_passages():
    base = FixedRetriever()

    results = FormFilterRetriever(base, KNOWN_FORMS).search("Translation rules for Form I-485?", k=5)

    assert ids(results) == ["I-485-0009", "I-485-0021"]
    assert base.requested_k == [200]


def test_query_without_a_form_is_passed_through():
    base = FixedRetriever()

    results = FormFilterRetriever(base, KNOWN_FORMS).search("Do I need a translation?", k=2)

    assert ids(results) == ["I-765-0090", "I-131-0061"]
    assert base.requested_k == [2]


def test_forms_are_detected_case_insensitively_and_combined():
    retriever = FormFilterRetriever(FixedRetriever(), KNOWN_FORMS)

    assert retriever.forms_named_in("file i-765 with a pending Form I-485") == {FormId("I-765"), FormId("I-485")}


def test_forms_that_are_not_loaded_are_ignored():
    retriever = FormFilterRetriever(FixedRetriever(), KNOWN_FORMS)

    results = retriever.search("Who must submit Form I-864?", k=1)

    assert retriever.forms_named_in("Who must submit Form I-864?") == set()
    assert ids(results) == ["I-765-0090"]


def test_name_shows_the_wrapping():
    assert FormFilterRetriever(FixedRetriever(), KNOWN_FORMS).name == "fixed+formfilter"
