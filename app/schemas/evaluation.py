from pydantic import BaseModel, ConfigDict

from app.schemas.timezone import BeijingDateTime


class EvaluationCaseResultRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    case_key: str
    question: str
    expected_document_title: str
    top1_document_title: str | None
    top1_hit: bool
    recall_hit: bool
    retrieved_count: int
    candidate_titles_json: str


class EvaluationRunRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    knowledge_base_id: int
    dataset_name: str
    total_cases: int
    top1_hit_count: int
    recall_hit_count: int
    average_keyword_latency_ms: int
    average_vector_latency_ms: int
    average_fusion_latency_ms: int
    average_rerank_latency_ms: int
    created_at: BeijingDateTime
    results: list[EvaluationCaseResultRead]
