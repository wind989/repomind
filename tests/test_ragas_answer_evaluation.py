import json
import warnings

import pytest

from app.services import ragas_answer_evaluation as answer_evaluation
from scripts.evaluate_ragas_answers import load_answer_samples


def test_load_answer_samples_accepts_question_answer_aliases(tmp_path) -> None:
    path = tmp_path / "answers.json"
    path.write_text(
        json.dumps(
            {
                "dataset_name": "测试回答题集",
                "samples": [
                    {
                        "case_key": "case-1",
                        "question": "问题",
                        "retrieved_contexts": ["上下文"],
                        "answer": "回答",
                        "reference_answer": "参考回答",
                    }
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    dataset_name, samples = load_answer_samples(path)

    assert dataset_name == "测试回答题集"
    assert samples[0].user_input == "问题"
    assert samples[0].response == "回答"
    assert samples[0].reference == "参考回答"


def test_answer_evaluation_requires_explicit_model() -> None:
    sample = answer_evaluation.AnswerEvaluationSample(
        case_key="case-1",
        user_input="问题",
        retrieved_contexts=["上下文"],
        response="回答",
    )

    with pytest.raises(ValueError, match="必须显式提供评测模型"):
        answer_evaluation.evaluate_answer_quality([sample], evaluator_llm=None)


def test_answer_relevancy_requires_embeddings() -> None:
    sample = answer_evaluation.AnswerEvaluationSample(
        case_key="case-1",
        user_input="问题",
        retrieved_contexts=["上下文"],
        response="回答",
    )

    with pytest.raises(ValueError, match="需要显式提供评测向量模型"):
        answer_evaluation.evaluate_answer_quality(
            [sample],
            evaluator_llm=object(),
            include_answer_relevancy=True,
        )


def test_factual_correctness_requires_reference() -> None:
    sample = answer_evaluation.AnswerEvaluationSample(
        case_key="case-1",
        user_input="问题",
        retrieved_contexts=["上下文"],
        response="回答",
    )

    with pytest.raises(ValueError, match="每道题都提供 reference"):
        answer_evaluation.evaluate_answer_quality(
            [sample],
            evaluator_llm=object(),
            include_factual_correctness=True,
        )


def test_answer_evaluation_maps_opt_in_metric_scores(monkeypatch) -> None:
    class FakeMetric:
        values_by_name = {
            "faithfulness": [0.8, 0.6],
            "answer_relevancy": [0.7, 0.5],
            "factual_correctness": [0.9, 0.4],
        }

        def __init__(self, llm, embeddings=None) -> None:
            self.name = type(self).__name__.lower()

        def single_turn_score(self, sample) -> float:
            metric_name = {
                "fakemetric": "faithfulness",
            }.get(self.name, self.name)
            return self.values_by_name[metric_name].pop(0)

    class FakeFaithfulness(FakeMetric):
        name = "faithfulness"

        def __init__(self, llm) -> None:
            self.metric_name = "faithfulness"

        def single_turn_score(self, sample) -> float:
            return self.values_by_name[self.metric_name].pop(0)

    class FakeResponseRelevancy(FakeMetric):
        def __init__(self, llm, embeddings, strictness) -> None:
            self.metric_name = "answer_relevancy"
            assert strictness == 1

        def single_turn_score(self, sample) -> float:
            return self.values_by_name[self.metric_name].pop(0)

    class FakeFactualCorrectness(FakeMetric):
        def __init__(self, llm) -> None:
            self.metric_name = "factual_correctness"

        def single_turn_score(self, sample) -> float:
            return self.values_by_name[self.metric_name].pop(0)

    import ragas.metrics

    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", category=DeprecationWarning)
        monkeypatch.setattr(ragas.metrics, "Faithfulness", FakeFaithfulness)
        monkeypatch.setattr(ragas.metrics, "ResponseRelevancy", FakeResponseRelevancy)
        monkeypatch.setattr(ragas.metrics, "FactualCorrectness", FakeFactualCorrectness)
    samples = [
        answer_evaluation.AnswerEvaluationSample(
            case_key="case-1",
            user_input="问题一",
            retrieved_contexts=["上下文一"],
            response="回答一",
            reference="参考一",
        ),
        answer_evaluation.AnswerEvaluationSample(
            case_key="case-2",
            user_input="问题二",
            retrieved_contexts=["上下文二"],
            response="回答二",
            reference="参考二",
        ),
    ]

    evaluation = answer_evaluation.evaluate_answer_quality(
        samples,
        evaluator_llm=object(),
        evaluator_embeddings=object(),
        include_answer_relevancy=True,
        include_factual_correctness=True,
    )

    assert evaluation.faithfulness_scores == [0.8, 0.6]
    assert evaluation.answer_relevancy_scores == [0.7, 0.5]
    assert evaluation.factual_correctness_scores == [0.9, 0.4]
    assert evaluation.average_faithfulness == 0.7
