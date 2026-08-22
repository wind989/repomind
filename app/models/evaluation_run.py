from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.core.timezone import beijing_now

if TYPE_CHECKING:
    from app.models.evaluation_case_result import EvaluationCaseResult
    from app.models.knowledge_base import KnowledgeBase


class EvaluationRun(Base):
    __tablename__ = "evaluation_runs"

    id: Mapped[int] = mapped_column(primary_key=True)
    knowledge_base_id: Mapped[int] = mapped_column(
        ForeignKey("knowledge_bases.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    dataset_name: Mapped[str] = mapped_column(String(100), nullable=False)
    total_cases: Mapped[int] = mapped_column(Integer, nullable=False)
    top1_hit_count: Mapped[int] = mapped_column(Integer, nullable=False)
    recall_hit_count: Mapped[int] = mapped_column(Integer, nullable=False)
    # Nullable keeps evaluation runs created before the MRR migration honest.
    mrr: Mapped[float | None] = mapped_column(Float, nullable=True)
    # Ragas ID-based context metrics are nullable for runs created before the
    # Ragas migration or for intentionally retrieval-only legacy records.
    ragas_context_precision: Mapped[float | None] = mapped_column(Float, nullable=True)
    ragas_context_recall: Mapped[float | None] = mapped_column(Float, nullable=True)
    average_keyword_latency_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    average_vector_latency_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    average_fusion_latency_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    average_rerank_latency_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=beijing_now, nullable=False)

    knowledge_base: Mapped["KnowledgeBase"] = relationship(back_populates="evaluation_runs")
    results: Mapped[list["EvaluationCaseResult"]] = relationship(
        back_populates="evaluation_run",
        cascade="all, delete-orphan",
        order_by="EvaluationCaseResult.id",
    )
