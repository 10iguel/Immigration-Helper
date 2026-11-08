import json

import pytest

from immigration_helper.evaluation import AnswerTarget, EvalQuestion, EvalSetStore, QuestionStyle
from immigration_helper.models import FormId
from tests.factories import make_chunk

TARGET = AnswerTarget(
    id="t01",
    form=FormId("I-765"),
    answer_phrases=("Adjustment Applicant under Section 245--(c)(9)",),
    reference_answer="File with Form I-485.",
)


def test_chunk_containing_phrase_answers_target_ignoring_case_and_spacing():
    chunk = make_chunk("1. adjustment applicant  under\nSection 245--(c)(9). File Form I-765 together with Form I-485.")

    assert TARGET.is_answered_by(chunk)


def test_chunk_from_another_form_does_not_answer_target():
    chunk = make_chunk("Adjustment Applicant under Section 245--(c)(9)", form="I-485")

    assert not TARGET.is_answered_by(chunk)


def test_target_requires_answer_phrases():
    with pytest.raises(ValueError):
        AnswerTarget(id="t02", form=FormId("I-765"), answer_phrases=(), reference_answer="")


def test_only_out_of_scope_questions_may_lack_a_target():
    with pytest.raises(ValueError):
        EvalQuestion(id="q", text="Where do I file?", style=QuestionStyle.PLAIN, target=None)


def test_store_expands_each_target_into_one_question_per_style(tmp_path):
    path = tmp_path / "eval_set.json"
    path.write_text(json.dumps({
        "targets": [{
            "id": "t01",
            "form": "I-765",
            "questions": {"plain": "Can I work while I wait?", "jargon": "How do I file under (c)(9)?"},
            "answer_phrases": ["Section 245--(c)(9)"],
            "reference_answer": "File with Form I-485.",
        }],
        "out_of_scope": [{"id": "o01", "question": "How do I become a citizen?"}],
    }), encoding="utf-8")

    questions = EvalSetStore(path).load()

    assert [(q.id, q.style) for q in questions] == [
        ("t01-plain", QuestionStyle.PLAIN),
        ("t01-jargon", QuestionStyle.JARGON),
        ("o01", QuestionStyle.OUT_OF_SCOPE),
    ]
    assert questions[0].target == questions[1].target
