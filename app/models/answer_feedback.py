from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.core.timezone import beijing_now

if TYPE_CHECKING:
    from app.models.retrieval_log import RetrievalLog


class AnswerFeedback(Base):
    __tablename__ = "answer_feedback"

    id: Mapped[int] = mapped_column(primary_key=True)
    retrieval_log_id: Mapped[int] = mapped_column(
        ForeignKey("retrieval_logs.id", ondelete="CASCADE"),
        unique=True,
        index=True,
        nullable=False,
    )
    helpful: Mapped[bool] = mapped_column(Boolean, nullable=False)
    comment: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=beijing_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=beijing_now,
        onupdate=beijing_now,
        nullable=False,
    )

    retrieval_log: Mapped["RetrievalLog"] = relationship(back_populates="feedback")
