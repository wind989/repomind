from typing import TYPE_CHECKING

from sqlalchemy import Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.retrieval_log import RetrievalLog


class AnswerCitation(Base):
    __tablename__ = "answer_citations"

    id: Mapped[int] = mapped_column(primary_key=True)
    retrieval_log_id: Mapped[int] = mapped_column(
        ForeignKey("retrieval_logs.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    document_id: Mapped[int] = mapped_column(Integer, nullable=False)
    document_chunk_id: Mapped[int] = mapped_column(Integer, nullable=False)
    citation_rank: Mapped[int] = mapped_column(Integer, nullable=False)
    distance: Mapped[float | None] = mapped_column(Float, nullable=True)
    document_title: Mapped[str] = mapped_column(String(200), nullable=False)
    content_excerpt: Mapped[str] = mapped_column(Text, nullable=False)

    retrieval_log: Mapped["RetrievalLog"] = relationship(back_populates="citations")
