from immigration_helper.answering import Answer, Citation
from immigration_helper.chat_model import ChatResult, ChatUsage
from immigration_helper.evaluation import AnswerTarget, EvalQuestion, QuestionStyle
from immigration_helper.evaluation.answer_eval import AnswerEvaluator, summarize_answers
from immigration_helper.evaluation.judge import AnswerJudge, Correctness, Support
from immigration_helper.models import FormId
from tests.factories import make_chunk

PASSAGE = make_chunk("You must also submit a full English translation.", form="I-485", chunk_id="I-485-0009")
USAGE = ChatUsage(1000, 100, 0.0028)
TARGET = AnswerTarget("t24", FormId("I-485"), ("full English translation",), "Yes, submit a full English translation.")
PLAIN = EvalQuestion("t24-plain", "Do I need to translate my birth certificate?", QuestionStyle.PLAIN, TARGET)
JARGON = EvalQuestion("t24-jargon", "What are the translation requirements for Form I-485?", QuestionStyle.JARGON, TARGET)
OUT_OF_SCOPE = EvalQuestion("o01", "How do I become a citizen?", QuestionStyle.OUT_OF_SCOPE, None)


def make_answer(question: str, answerable: bool, text: str) -> Answer:
    citations = (Citation.of(PASSAGE),) if answerable else ()
    return Answer(question, answerable, text, citations, (), USAGE, (PASSAGE,))


class FakeJudgeModel:
    model = "fake-judge"

    def __init__(self, verdicts: dict[str, dict]):
        self._verdicts = verdicts  # keyed by a word that appears in the question
        self.prompts: list[str] = []

    def complete_json(self, messages: list[dict], schema: dict, schema_name: str) -> ChatResult:
        prompt = messages[-1]["content"]
        self.prompts.append(prompt)
        key = next(word for word in self._verdicts if word in prompt)
        return ChatResult(self._verdicts[key], USAGE)


def verdict(correctness: str, support: str = "full", advice: bool = False, claims: list[str] | None = None) -> dict:
    return {"reasoning": "…", "unsupported_claims": claims or [], "support": support,
            "correctness": correctness, "gives_advice": advice}


class FakeAnswerer:
    def __init__(self, answers: dict[str, Answer]):
        self._answers = answers

    def answer(self, question: str) -> Answer:
        return self._answers[question]


def test_judge_sees_passages_answer_and_reference_and_parses_the_verdict():
    model = FakeJudgeModel({"translate": verdict("partial", support="partial", claims=["Originals are required."])})
    answer = make_answer(PLAIN.text, True, "Yes, and send the original.")

    result = AnswerJudge(model).judge(answer, TARGET.reference_answer)

    assert result.correctness is Correctness.PARTIAL
    assert result.support is Support.PARTIAL
    assert result.unsupported_claims == ("Originals are required.",)
    assert "[I-485-0009]" in model.prompts[0]
    assert "Assistant's answer:\nYes, and send the original." in model.prompts[0]
    assert "Reference answer: Yes, submit a full English translation." in model.prompts[0]


def test_judge_is_told_when_there_is_no_reference_answer():
    model = FakeJudgeModel({"citizen": verdict("not_applicable")})

    AnswerJudge(model).judge(make_answer(OUT_OF_SCOPE.text, False, "Not covered."), None)

    assert "The loaded instructions do not answer this question" in model.prompts[0]


def test_summary_counts_correct_answers_and_declined_out_of_scope_questions():
    answers = {
        PLAIN.text: make_answer(PLAIN.text, True, "Yes."),
        JARGON.text: make_answer(JARGON.text, True, "Yes."),
        OUT_OF_SCOPE.text: make_answer(OUT_OF_SCOPE.text, False, "The instructions don't cover this."),
    }
    judge = AnswerJudge(FakeJudgeModel({
        "translate my": verdict("correct"),
        "requirements": verdict("incorrect", advice=True),
        "citizen": verdict("not_applicable"),
    }))
    evaluator = AnswerEvaluator(FakeAnswerer(answers), judge)

    results = [evaluator.evaluate_one(question) for question in (PLAIN, JARGON, OUT_OF_SCOPE)]
    summaries = {summary.group: summary for summary in summarize_answers(results)}

    assert summaries["answerable"].questions == 2
    assert summaries["answerable"].correct == 0.5
    assert summaries["answerable"].gives_advice == 0.5
    assert summaries["plain"].correct == 1.0
    assert summaries["out_of_scope"].correct == 1.0
    assert summaries["out_of_scope"].declined == 1.0


def test_declining_an_answerable_question_is_incorrect_even_if_the_judge_says_correct():
    declined = make_answer(PLAIN.text, False, "The instructions don't cover this.")
    judge = AnswerJudge(FakeJudgeModel({"translate": verdict("correct")}))

    result = AnswerEvaluator(FakeAnswerer({PLAIN.text: declined}), judge).evaluate_one(PLAIN)

    assert not result.is_correct
    assert not result.is_partially_correct
