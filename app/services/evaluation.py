import json
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.models.evaluation_case_result import EvaluationCaseResult
from app.models.evaluation_run import EvaluationRun
from app.models.knowledge_base import KnowledgeBase
from app.services.ragas_evaluation import evaluate_document_contexts
from app.services.rag import VectorStore, hybrid_retrieve


@dataclass(frozen=True)
class EvaluationCase:
    case_key: str
    knowledge_base_id: int
    question: str
    expected_document_title: str


def evaluate_retrieval_cases(
    db: Session,
    cases: list[EvaluationCase],
    dataset_name: str,
    vector_store: VectorStore,
    recall_k: int = 8,
) -> EvaluationRun:
    if not cases:
        raise ValueError("评测题集不能为空")
    knowledge_base_ids = {case.knowledge_base_id for case in cases}
    if len(knowledge_base_ids) != 1:
        raise ValueError("一次评测只能针对一个知识库")
    knowledge_base_id = knowledge_base_ids.pop()
    if db.get(KnowledgeBase, knowledge_base_id) is None:
        raise ValueError("评测知识库不存在")

    keyword_latencies: list[int] = []
    vector_latencies: list[int] = []
    fusion_latencies: list[int] = []
    rerank_latencies: list[int] = []
    results: list[EvaluationCaseResult] = []
    top1_hit_count = 0
    recall_hit_count = 0
    reciprocal_ranks: list[float] = []
    ragas_samples: list[tuple[str, list[str], str]] = []

    for case in cases:
        retrieval = hybrid_retrieve(db, knowledge_base_id, case.question, vector_store, recall_k)
        candidate_titles = [candidate.document_title for candidate in retrieval.candidates]
        top1_document_title = candidate_titles[0] if candidate_titles else None
        top1_hit = top1_document_title == case.expected_document_title
        expected_rank = next(
            (
                rank
                for rank, title in enumerate(candidate_titles, start=1)
                if title == case.expected_document_title
            ),
            None,
        )
        recall_hit = expected_rank is not None and expected_rank <= recall_k
        top1_hit_count += int(top1_hit)
        recall_hit_count += int(recall_hit)
        reciprocal_ranks.append(1 / expected_rank if expected_rank is not None else 0.0)
        ragas_samples.append(
            (
                case.question,
                list(dict.fromkeys(candidate_titles)),
                case.expected_document_title,
            )
        )
        keyword_latencies.append(retrieval.keyword_latency_ms)
        vector_latencies.append(retrieval.vector_latency_ms)
        fusion_latencies.append(retrieval.fusion_latency_ms)
        rerank_latencies.append(retrieval.rerank_latency_ms)
        results.append(
            EvaluationCaseResult(
                case_key=case.case_key,
                question=case.question,
                expected_document_title=case.expected_document_title,
                top1_document_title=top1_document_title,
                top1_hit=top1_hit,
                recall_hit=recall_hit,
                expected_rank=expected_rank,
                retrieved_count=len(retrieval.candidates),
                candidate_titles_json=json.dumps(candidate_titles, ensure_ascii=False),
            )
        )

    ragas_evaluation = evaluate_document_contexts(ragas_samples)
    for result, precision, recall in zip(
        results,
        ragas_evaluation.precision_scores,
        ragas_evaluation.recall_scores,
    ):
        result.ragas_context_precision = precision
        result.ragas_context_recall = recall

    total_cases = len(cases)
    evaluation_run = EvaluationRun(
        knowledge_base_id=knowledge_base_id,
        dataset_name=dataset_name,
        total_cases=total_cases,
        top1_hit_count=top1_hit_count,
        recall_hit_count=recall_hit_count,
        mrr=round(sum(reciprocal_ranks) / total_cases, 4),
        ragas_context_precision=ragas_evaluation.average_precision,
        ragas_context_recall=ragas_evaluation.average_recall,
        average_keyword_latency_ms=round(sum(keyword_latencies) / total_cases),
        average_vector_latency_ms=round(sum(vector_latencies) / total_cases),
        average_fusion_latency_ms=round(sum(fusion_latencies) / total_cases),
        average_rerank_latency_ms=round(sum(rerank_latencies) / total_cases),
    )
    evaluation_run.results = results
    return evaluation_run
