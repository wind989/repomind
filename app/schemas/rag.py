from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


class AskRequest(BaseModel):
    question: str = Field(min_length=1, max_length=1000, examples=["创建订单接口需要什么参数？"])
    top_k: int = Field(default=3, ge=1, le=5)
    recall_k: int = Field(default=8, ge=1, le=20)

    @field_validator("question")
    @classmethod
    def normalize_question(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("问题不能只包含空白字符")
        return value


class KnowledgeBaseIndexResult(BaseModel):
    knowledge_base_id: int
    indexed_chunk_count: int


class CitationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    document_id: int
    document_chunk_id: int
    citation_rank: int
    distance: float | None
    document_title: str
    content_excerpt: str


class AskResponse(BaseModel):
    retrieval_log_id: int
    answer: str
    citations: list[CitationRead]


class FeedbackUpsert(BaseModel):
    helpful: bool
    comment: str | None = Field(default=None, max_length=500)

    @field_validator("comment")
    @classmethod
    def normalize_comment(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        return value or None


class FeedbackRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    retrieval_log_id: int
    helpful: bool
    comment: str | None
    created_at: datetime
    updated_at: datetime


class RetrievalCandidateRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    document_id: int
    document_chunk_id: int
    document_title: str
    content_excerpt: str
    keyword_rank: int | None
    keyword_score: float | None
    vector_rank: int | None
    vector_distance: float | None
    rrf_score: float
    rerank_score: float
    final_rank: int


class RetrievalLogRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    knowledge_base_id: int
    question: str
    answer: str
    model_name: str
    retrieved_count: int
    keyword_latency_ms: int
    vector_latency_ms: int
    fusion_latency_ms: int
    rerank_latency_ms: int
    latency_ms: int
    created_at: datetime
    citations: list[CitationRead]
    candidates: list[RetrievalCandidateRead]
    feedback: FeedbackRead | None
