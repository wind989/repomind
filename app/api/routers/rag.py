import logging
from typing import Annotated, cast

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.api.routers.knowledge_bases import get_knowledge_base_or_404
from app.core.config import get_settings
from app.db.session import get_db
from app.models.answer_citation import AnswerCitation
from app.models.answer_feedback import AnswerFeedback
from app.models.chat_message import ChatMessage
from app.models.document import Document
from app.models.document_chunk import DocumentChunk
from app.models.retrieval_log import RetrievalLog
from app.models.retrieval_candidate import RetrievalCandidate
from app.models.evaluation_run import EvaluationRun
from app.schemas.evaluation import EvaluationRunRead
from app.schemas.rag import (
    AskRequest,
    AskResponse,
    CitationRead,
    FeedbackRead,
    FeedbackUpsert,
    KnowledgeBaseIndexResult,
    RetrievalLogRead,
)
from app.services.rag import (
    AnswerGenerator,
    IndexableChunk,
    RagServiceError,
    VectorStore,
    candidates_to_evidence,
    get_answer_generator,
    get_vector_store,
    hybrid_retrieve,
    measure_answer_generation,
)

router = APIRouter(tags=["RAG"])
logger = logging.getLogger("repomind.retrieval")


def get_app_vector_store(request: Request) -> VectorStore:
    overridden_store = getattr(request.app.state, "vector_store", None)
    return cast(VectorStore, overridden_store) if overridden_store is not None else get_vector_store()


def get_app_answer_generator(request: Request) -> AnswerGenerator:
    overridden_generator = getattr(request.app.state, "answer_generator", None)
    return cast(AnswerGenerator, overridden_generator) if overridden_generator is not None else get_answer_generator()


@router.post(
    "/knowledge-bases/{knowledge_base_id}/index",
    response_model=KnowledgeBaseIndexResult,
)
def index_knowledge_base(
    knowledge_base_id: int,
    request: Request,
    db: Session = Depends(get_db),
) -> KnowledgeBaseIndexResult:
    get_knowledge_base_or_404(db, knowledge_base_id)
    rows = (
        db.query(DocumentChunk, Document)
        .join(Document, DocumentChunk.document_id == Document.id)
        .filter(Document.knowledge_base_id == knowledge_base_id)
        .order_by(Document.id.asc(), DocumentChunk.chunk_index.asc())
        .all()
    )
    if not rows:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="知识库尚无可索引的文档片段，请先上传并完成文档处理",
        )

    chunks = [
        IndexableChunk(
            chunk_id=chunk.id,
            document_id=document.id,
            document_title=document.title,
            chunk_index=chunk.chunk_index,
            content=chunk.content,
        )
        for chunk, document in rows
    ]
    try:
        indexed_count = get_app_vector_store(request).replace_knowledge_base(knowledge_base_id, chunks)
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="向量索引服务暂不可用") from exc

    return KnowledgeBaseIndexResult(knowledge_base_id=knowledge_base_id, indexed_chunk_count=indexed_count)


@router.post(
    "/knowledge-bases/{knowledge_base_id}/ask",
    response_model=AskResponse,
)
def ask_knowledge_base(
    knowledge_base_id: int,
    payload: AskRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> AskResponse:
    get_knowledge_base_or_404(db, knowledge_base_id)
    try:
        retrieval_result = hybrid_retrieve(
            db,
            knowledge_base_id,
            payload.question,
            get_app_vector_store(request),
            payload.recall_k,
        )
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="检索服务暂不可用") from exc

    if not retrieval_result.candidates or not any(
        item.vector_rank is not None for item in retrieval_result.candidates
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="知识库尚未建立可用索引，或没有匹配的文档片段",
        )
    selected_candidates = retrieval_result.candidates[: payload.top_k]
    evidence = candidates_to_evidence(selected_candidates)

    try:
        answer, latency_ms = measure_answer_generation(
            get_app_answer_generator(request),
            payload.question,
            evidence,
        )
    except RagServiceError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="问答模型服务暂不可用") from exc

    retrieval_log = RetrievalLog(
        knowledge_base_id=knowledge_base_id,
        question=payload.question,
        answer=answer,
        model_name=get_settings().deepseek_model,
        retrieved_count=len(evidence),
        keyword_latency_ms=retrieval_result.keyword_latency_ms,
        vector_latency_ms=retrieval_result.vector_latency_ms,
        fusion_latency_ms=retrieval_result.fusion_latency_ms,
        rerank_latency_ms=retrieval_result.rerank_latency_ms,
        latency_ms=latency_ms,
    )
    db.add_all(
        [
            ChatMessage(knowledge_base_id=knowledge_base_id, role="user", content=payload.question),
            ChatMessage(knowledge_base_id=knowledge_base_id, role="assistant", content=answer),
            retrieval_log,
        ]
    )
    retrieval_log.citations = [
        AnswerCitation(
            document_id=item.document_id,
            document_chunk_id=item.chunk_id,
            citation_rank=rank,
            distance=item.vector_distance,
            document_title=item.document_title,
            content_excerpt=item.content[:1000],
        )
        for rank, item in enumerate(selected_candidates, start=1)
    ]
    retrieval_log.candidates = [
        RetrievalCandidate(
            document_id=item.document_id,
            document_chunk_id=item.chunk_id,
            document_title=item.document_title,
            content_excerpt=item.content[:1000],
            keyword_rank=item.keyword_rank,
            keyword_score=item.keyword_score,
            vector_rank=item.vector_rank,
            vector_distance=item.vector_distance,
            rrf_score=item.rrf_score,
            rerank_score=item.rerank_score,
            final_rank=item.final_rank,
        )
        for item in retrieval_result.candidates
    ]
    try:
        db.commit()
        db.refresh(retrieval_log)
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="问答记录保存失败") from exc

    logger.info(
        "retrieval_completed",
        extra={
            "knowledge_base_id": knowledge_base_id,
            "retrieval_log_id": retrieval_log.id,
            "retrieved_count": retrieval_log.retrieved_count,
            "keyword_latency_ms": retrieval_log.keyword_latency_ms,
            "vector_latency_ms": retrieval_log.vector_latency_ms,
            "fusion_latency_ms": retrieval_log.fusion_latency_ms,
            "rerank_latency_ms": retrieval_log.rerank_latency_ms,
            "latency_ms": retrieval_log.latency_ms,
        },
    )
    return AskResponse(
        retrieval_log_id=retrieval_log.id,
        answer=answer,
        citations=[CitationRead.model_validate(item) for item in retrieval_log.citations],
    )


@router.get("/retrieval-logs", response_model=list[RetrievalLogRead])
def list_retrieval_logs(
    db: Session = Depends(get_db),
    knowledge_base_id: Annotated[int | None, Query(ge=1)] = None,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> list[RetrievalLog]:
    query = db.query(RetrievalLog)
    if knowledge_base_id is not None:
        query = query.filter(RetrievalLog.knowledge_base_id == knowledge_base_id)
    return query.order_by(RetrievalLog.id.desc()).offset(offset).limit(limit).all()


@router.get("/retrieval-logs/{retrieval_log_id}", response_model=RetrievalLogRead)
def get_retrieval_log(retrieval_log_id: int, db: Session = Depends(get_db)) -> RetrievalLog:
    retrieval_log = db.get(RetrievalLog, retrieval_log_id)
    if retrieval_log is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="检索日志不存在")
    return retrieval_log


@router.put("/retrieval-logs/{retrieval_log_id}/feedback", response_model=FeedbackRead)
def upsert_answer_feedback(
    retrieval_log_id: int,
    payload: FeedbackUpsert,
    db: Session = Depends(get_db),
) -> AnswerFeedback:
    retrieval_log = db.get(RetrievalLog, retrieval_log_id)
    if retrieval_log is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="问答记录不存在")

    feedback = retrieval_log.feedback
    if feedback is None:
        feedback = AnswerFeedback(retrieval_log_id=retrieval_log_id, **payload.model_dump())
        db.add(feedback)
    else:
        feedback.helpful = payload.helpful
        feedback.comment = payload.comment
    try:
        db.commit()
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="反馈保存失败") from exc
    db.refresh(feedback)
    return feedback


@router.get("/retrieval-logs/{retrieval_log_id}/feedback", response_model=FeedbackRead)
def get_answer_feedback(retrieval_log_id: int, db: Session = Depends(get_db)) -> AnswerFeedback:
    retrieval_log = db.get(RetrievalLog, retrieval_log_id)
    if retrieval_log is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="问答记录不存在")
    if retrieval_log.feedback is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="该问答尚未收到反馈")
    return retrieval_log.feedback


@router.get("/evaluation-runs", response_model=list[EvaluationRunRead])
def list_evaluation_runs(
    db: Session = Depends(get_db),
    knowledge_base_id: Annotated[int | None, Query(ge=1)] = None,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> list[EvaluationRun]:
    query = db.query(EvaluationRun)
    if knowledge_base_id is not None:
        query = query.filter(EvaluationRun.knowledge_base_id == knowledge_base_id)
    return query.order_by(EvaluationRun.id.desc()).offset(offset).limit(limit).all()


@router.get("/evaluation-runs/{evaluation_run_id}", response_model=EvaluationRunRead)
def get_evaluation_run(evaluation_run_id: int, db: Session = Depends(get_db)) -> EvaluationRun:
    evaluation_run = db.get(EvaluationRun, evaluation_run_id)
    if evaluation_run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="评测运行记录不存在")
    return evaluation_run
