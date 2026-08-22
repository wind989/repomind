"""Ragas-backed, deterministic context evaluation helpers.

The default RepoMind evaluation does not call an LLM.  It uses Ragas' ID-based
context metrics over document-level identifiers so the result is reproducible
in local development and CI.  End-to-end answer metrics such as faithfulness
remain an explicit, model-backed extension rather than an implicit network
call during ordinary retrieval evaluation.
"""

from __future__ import annotations

import math
import warnings
from dataclasses import dataclass
from typing import Sequence


@dataclass(frozen=True)
class RagasContextEvaluation:
    precision_scores: list[float]
    recall_scores: list[float]

    @property
    def average_precision(self) -> float:
        return round(sum(self.precision_scores) / len(self.precision_scores), 4)

    @property
    def average_recall(self) -> float:
        return round(sum(self.recall_scores) / len(self.recall_scores), 4)


def evaluate_document_contexts(
    samples: Sequence[tuple[str, Sequence[str], str]],
) -> RagasContextEvaluation:
    """Evaluate document-level context precision and recall with Ragas.

    Each tuple contains ``(question, retrieved_document_ids, expected_document_id)``.
    IDs are deduplicated by the caller so the metrics answer a document-level
    question rather than counting repeated chunks from the same document.
    """

    if not samples:
        raise ValueError("Ragas 评测样本不能为空")

    try:
        from ragas import EvaluationDataset, SingleTurnSample, evaluate

        # These names remain available in Ragas 0.4.3 and are deprecated only
        # as import locations.  Suppress the advisory warning while keeping
        # the implementation pinned and reproducible for this project.
        with warnings.catch_warnings():
            warnings.filterwarnings(
                "ignore",
                message="Importing .* from 'ragas.metrics' is deprecated.*",
                category=DeprecationWarning,
            )
            from ragas.metrics import IDBasedContextPrecision, IDBasedContextRecall
    except ImportError as exc:  # pragma: no cover - exercised by broken installs
        raise RuntimeError(
            "Ragas 评测依赖未正确安装，请执行 pip install -r requirements.txt"
        ) from exc

    dataset = EvaluationDataset(
        samples=[
            SingleTurnSample(
                user_input=question,
                retrieved_context_ids=list(retrieved_ids),
                reference_context_ids=[expected_id],
            )
            for question, retrieved_ids, expected_id in samples
        ]
    )
    with warnings.catch_warnings():
        warnings.filterwarnings(
            "ignore",
            message="evaluate\\(\\) is deprecated.*",
            category=DeprecationWarning,
        )
        warnings.filterwarnings(
            "ignore",
            message="aevaluate\\(\\) is deprecated.*",
            category=DeprecationWarning,
        )
        result = evaluate(
            dataset=dataset,
            metrics=[IDBasedContextPrecision(), IDBasedContextRecall()],
            show_progress=False,
            raise_exceptions=True,
        )

    precision_scores = [_finite_score(value) for value in result["id_based_context_precision"]]
    recall_scores = [_finite_score(value) for value in result["id_based_context_recall"]]
    return RagasContextEvaluation(
        precision_scores=precision_scores,
        recall_scores=recall_scores,
    )


def _finite_score(value: object) -> float:
    try:
        score = float(value)
    except (TypeError, ValueError):
        return 0.0
    return round(score, 4) if math.isfinite(score) else 0.0
