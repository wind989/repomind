from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.answer_citation import AnswerCitation
    from app.models.answer_feedback import AnswerFeedback
    from app.models.knowledge_base import KnowledgeBase
    from app.models.retrieval_candidate import RetrievalCandidate


class RetrievalLog(Base):
    __tablename__ = "retrieval_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    knowledge_base_id: Mapped[int] = mapped_column(
        ForeignKey("knowledge_bases.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    question: Mapped[str] = mapped_column(Text, nullable=False)
    answer: Mapped[str] = mapped_column(Text, nullable=False)
    model_name: Mapped[str] = mapped_column(String(100), nullable=False)
    retrieved_count: Mapped[int] = mapped_column(Integer, nullable=False)
    keyword_latency_ms: Mapped[int] = mapped_column(Integer, server_default="0", nullable=False)
    vector_latency_ms: Mapped[int] = mapped_column(Integer, server_default="0", nullable=False)
    fusion_latency_ms: Mapped[int] = mapped_column(Integer, server_default="0", nullable=False)
    rerank_latency_ms: Mapped[int] = mapped_column(Integer, server_default="0", nullable=False)
    latency_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)

    knowledge_base: Mapped["KnowledgeBase"] = relationship(back_populates="retrieval_logs")
    citations: Mapped[list["AnswerCitation"]] = relationship(
        back_populates="retrieval_log",
        cascade="all, delete-orphan",
        order_by="AnswerCitation.citation_rank",
    )
    candidates: Mapped[list["RetrievalCandidate"]] = relationship(
        back_populates="retrieval_log",
        cascade="all, delete-orphan",
        order_by="RetrievalCandidate.final_rank",
    )
    feedback: Mapped["AnswerFeedback | None"] = relationship(
        back_populates="retrieval_log",
        cascade="all, delete-orphan",
        uselist=False,
    )
