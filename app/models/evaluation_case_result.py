from typing import TYPE_CHECKING

from sqlalchemy import Boolean, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.evaluation_run import EvaluationRun


class EvaluationCaseResult(Base):
    __tablename__ = "evaluation_case_results"
    __table_args__ = (
        UniqueConstraint("evaluation_run_id", "case_key", name="uq_evaluation_case_results_run_case"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    evaluation_run_id: Mapped[int] = mapped_column(
        ForeignKey("evaluation_runs.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    case_key: Mapped[str] = mapped_column(String(100), nullable=False)
    question: Mapped[str] = mapped_column(Text, nullable=False)
    expected_document_title: Mapped[str] = mapped_column(String(200), nullable=False)
    top1_document_title: Mapped[str | None] = mapped_column(String(200), nullable=True)
    top1_hit: Mapped[bool] = mapped_column(Boolean, nullable=False)
    recall_hit: Mapped[bool] = mapped_column(Boolean, nullable=False)
    expected_rank: Mapped[int | None] = mapped_column(Integer, nullable=True)
    retrieved_count: Mapped[int] = mapped_column(Integer, nullable=False)
    candidate_titles_json: Mapped[str] = mapped_column(Text, nullable=False)

    evaluation_run: Mapped["EvaluationRun"] = relationship(back_populates="results")
