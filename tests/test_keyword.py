from immigration_helper.retrieval.keyword import KeywordRetriever, tokenize
from tests.factories import make_chunk


def test_tokenize_keeps_uscis_codes_and_form_numbers():
    assert tokenize("File Form I-765 under (c)(9) with your A-Number.") == [
        "file", "form", "i-765", "under", "(c)", "(9)", "with", "your", "a-number",
    ]


def test_search_ranks_chunk_sharing_rare_terms_first():
    chunks = [
        make_chunk("Submit two passport-style photos.", chunk_id="I-765-0001"),
        make_chunk("Adjustment applicants file under category (c)(9) with Form I-485.", chunk_id="I-765-0002"),
        make_chunk("Asylum applicants file under category (c)(8).", chunk_id="I-765-0003"),
    ]

    results = KeywordRetriever(chunks).search("Which category is (c)(9)?", k=2)

    assert [result.chunk.id for result in results][0] == "I-765-0002"
    assert len(results) == 2


def test_search_matches_heading_path_too():
    chunks = [
        make_chunk("Provide the number.", chunk_id="I-765-0001", heading="Alien Registration Number"),
        make_chunk("Provide your date of birth.", chunk_id="I-765-0002", heading="Date of Birth"),
        make_chunk("Provide your place of birth.", chunk_id="I-765-0003", heading="Place of Birth"),
    ]

    results = KeywordRetriever(chunks).search("alien registration", k=1)

    assert results[0].chunk.id == "I-765-0001"
