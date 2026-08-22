"""Opt-in Ragas evaluation for generated answers.

The regular retrieval evaluation deliberately stays model-free.  This module
is only used by the explicit answer-quality evaluation script, where a caller
has supplied a model and accepted the associated network/cost boundary.
"""

from __future__ import annotations

import math
import warnings
from dataclasses import dataclass
from typing import Any, Sequence


@dataclass(frozen=True)
class AnswerEvaluationSample:
    """One completed RAG interaction to score."""

    case_key: str
    user_input: str
    retrieved_contexts: list[str]
    response: str
    reference: str | None = None


@dataclass(frozen=True)
class RagasAnswerEvaluation:
    """Per-case and aggregate scores returned by the answer evaluator."""

    faithfulness_scores: list[float]
    answer_relevancy_scores: list[float] | None = None
    factual_correctness_scores: list[float] | None = None

    @property
    def average_faithfulness(self) -> float:
        return _average(self.faithfulness_scores)

    @property
    def average_answer_relevancy(self) -> float | None:
        return _average(self.answer_relevancy_scores) if self.answer_relevancy_scores is not None else None

    @property
    def average_factual_correctness(self) -> float | None:
        return (
            _average(self.factual_correctness_scores)
            if self.factual_correctness_scores is not None
            else None
        )


def evaluate_answer_quality(
    samples: Sequence[AnswerEvaluationSample],
    *,
    evaluator_llm: Any,
    evaluator_embeddings: Any | None = None,
    include_answer_relevancy: bool = False,
    include_factual_correctness: bool = False,
) -> RagasAnswerEvaluation:
    """Run opt-in Ragas answer metrics against completed interactions.

    ``evaluator_llm`` is intentionally required so a normal retrieval run
    cannot silently start making external model calls.  Answer Relevancy
    additionally needs embeddings; Factual Correctness needs a reference
    answer for every sample.
    """

    if not samples:
        raise ValueError("回答评测样本不能为空")
    if evaluator_llm is None:
        raise ValueError("回答评测必须显式提供评测模型")
    if include_answer_relevancy and evaluator_embeddings is None:
        raise ValueError("Answer Relevancy 需要显式提供评测向量模型")
    if include_factual_correctness and any(sample.reference is None for sample in samples):
        raise ValueError("Factual Correctness 需要每道题都提供 reference")

    try:
        from ragas import SingleTurnSample

        # Ragas 0.4.3 keeps these legacy import names while the project pins
        # that version for reproducible CI.  Suppress only the import advice;
        # the opt-in script remains explicit about its model-backed behavior.
        with warnings.catch_warnings():
            warnings.filterwarnings(
                "ignore",
                message="Importing .* from 'ragas.metrics' is deprecated.*",
                category=DeprecationWarning,
            )
            from ragas.metrics import Faithfulness, FactualCorrectness, ResponseRelevancy
    except ImportError as exc:  # pragma: no cover - exercised by broken installs
        raise RuntimeError(
            "Ragas 回答评测依赖未正确安装，请执行 pip install -r requirements.txt"
        ) from exc

    metrics: list[Any] = [Faithfulness(llm=evaluator_llm)]
    if include_answer_relevancy:
        # DeepSeek's OpenAI-compatible endpoint currently accepts only one
        # completion per request.  Ragas defaults ``strictness`` to 3 for
        # ResponseRelevancy, which sends ``n=3`` and is rejected with HTTP
        # 400.  A single generated question keeps this opt-in metric
        # compatible with DeepSeek while retaining its normal score path.
        metrics.append(
            ResponseRelevancy(
                llm=evaluator_llm,
                embeddings=evaluator_embeddings,
                strictness=1,
            )
        )
    if include_factual_correctness:
        metrics.append(FactualCorrectness(llm=evaluator_llm))

    # Score one sample at a time rather than using evaluate().  Besides making
    # the case-to-score mapping explicit, this prevents Ragas' parallel
    # executor from leaving background tasks behind when a provider rejects a
    # request (for example, an exhausted balance).
    faithfulness_metric = metrics[0]
    answer_relevancy_metric = metrics[1] if include_answer_relevancy else None
    factual_correctness_metric = (
        metrics[-1] if include_factual_correctness else None
    )
    faithfulness_scores: list[float] = []
    answer_relevancy_scores: list[float] | None = [] if include_answer_relevancy else None
    factual_correctness_scores: list[float] | None = [] if include_factual_correctness else None
    for sample in samples:
        ragas_sample = SingleTurnSample(
            user_input=sample.user_input,
            retrieved_contexts=list(sample.retrieved_contexts),
            response=sample.response,
            reference=sample.reference,
        )
        faithfulness_scores.append(
            _finite_score(faithfulness_metric.single_turn_score(ragas_sample))
        )
        if answer_relevancy_metric is not None and answer_relevancy_scores is not None:
            answer_relevancy_scores.append(
                _finite_score(answer_relevancy_metric.single_turn_score(ragas_sample))
            )
        if factual_correctness_metric is not None and factual_correctness_scores is not None:
            factual_correctness_scores.append(
                _finite_score(factual_correctness_metric.single_turn_score(ragas_sample))
            )
    return RagasAnswerEvaluation(
        faithfulness_scores=faithfulness_scores,
        answer_relevancy_scores=answer_relevancy_scores,
        factual_correctness_scores=factual_correctness_scores,
    )


def build_deepseek_evaluator_llm() -> Any:
    """Build a DeepSeek-compatible LangChain evaluator without logging secrets."""

    from app.core.config import get_settings

    settings = get_settings()
    if not settings.deepseek_api_key:
        raise RuntimeError("DEEPSEEK_API_KEY 未配置，无法进行回答质量评测")

    try:
        from langchain_openai import ChatOpenAI
        from ragas.llms import LangchainLLMWrapper
    except ImportError as exc:  # pragma: no cover - exercised by broken installs
        raise RuntimeError(
            "回答质量评测需要 langchain-openai 和 ragas，请执行 pip install -r requirements.txt"
        ) from exc

    with warnings.catch_warnings():
        warnings.filterwarnings(
            "ignore",
            message="LangchainLLMWrapper is deprecated.*",
            category=DeprecationWarning,
        )
        chat_model = ChatOpenAI(
            api_key=settings.deepseek_api_key,
            base_url=settings.deepseek_base_url,
            model=settings.deepseek_model,
            temperature=0,
            extra_body={"thinking": {"type": "disabled"}},
        )
        return LangchainLLMWrapper(chat_model)


def build_chroma_evaluator_embeddings() -> Any:
    """Adapt the project's existing Chroma embedding function for Ragas.

    This path is opt-in because Chroma may initialize/download its local
    embedding model the first time it is used.
    """

    try:
        from langchain_core.embeddings import Embeddings
        from ragas.embeddings import LangchainEmbeddingsWrapper
        from app.services.rag import get_vector_store
    except ImportError as exc:  # pragma: no cover - exercised by broken installs
        raise RuntimeError(
            "Answer Relevancy 需要 LangChain、Ragas 和 Chroma 依赖"
        ) from exc

    embedding_function = get_vector_store().collection._embedding_function

    class ChromaEmbeddings(Embeddings):
        def embed_documents(self, texts: list[str]) -> list[list[float]]:
            vectors = embedding_function(texts)
            return [_as_float_list(vector) for vector in vectors]

        def embed_query(self, text: str) -> list[float]:
            return self.embed_documents([text])[0]

    with warnings.catch_warnings():
        warnings.filterwarnings(
            "ignore",
            message="LangchainEmbeddingsWrapper is deprecated.*",
            category=DeprecationWarning,
        )
        return LangchainEmbeddingsWrapper(ChromaEmbeddings())


def _finite_score(value: object) -> float:
    try:
        score = float(value)
    except (TypeError, ValueError):
        return 0.0
    return round(score, 4) if math.isfinite(score) else 0.0


def _average(scores: Sequence[float]) -> float:
    if not scores:
        raise ValueError("评测分数不能为空")
    return round(sum(scores) / len(scores), 4)


def _as_float_list(vector: Any) -> list[float]:
    values = vector.tolist() if hasattr(vector, "tolist") else vector
    return [float(value) for value in values]
