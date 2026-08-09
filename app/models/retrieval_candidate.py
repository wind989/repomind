from typing import TYPE_CHECKING

from sqlalchemy import Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.retrieval_log import RetrievalLog


class RetrievalCandidate(Base):
    __tablename__ = "retrieval_candidates"

    id: Mapped[int] = mapped_column(primary_key=True)
    retrieval_log_id: Mapped[int] = mapped_column(
        ForeignKey("retrieval_logs.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    document_id: Mapped[int] = mapped_column(Integer, nullable=False)
    document_chunk_id: Mapped[int] = mapped_column(Integer, nullable=False)
    document_title: Mapped[str] = mapped_column(String(200), nullable=False)
    content_excerpt: Mapped[str] = mapped_column(Text, nullable=False)
    keyword_rank: Mapped[int | None] = mapped_column(Integer, nullable=True)
    keyword_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    vector_rank: Mapped[int | None] = mapped_column(Integer, nullable=True)
    vector_distance: Mapped[float | None] = mapped_column(Float, nullable=True)
    rrf_score: Mapped[float] = mapped_column(Float, nullable=False)
    rerank_score: Mapped[float] = mapped_column(Float, nullable=False)
    final_rank: Mapped[int] = mapped_column(Integer, nullable=False)

    retrieval_log: Mapped["RetrievalLog"] = relationship(back_populates="candidates")
