from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.chat_message import ChatMessage
    from app.models.document import Document
    from app.models.evaluation_run import EvaluationRun
    from app.models.retrieval_log import RetrievalLog


class KnowledgeBase(Base):
    __tablename__ = "knowledge_bases"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, index=True, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    documents: Mapped[list["Document"]] = relationship(
        back_populates="knowledge_base",
        cascade="all, delete-orphan",
    )
    chat_messages: Mapped[list["ChatMessage"]] = relationship(
        back_populates="knowledge_base",
        cascade="all, delete-orphan",
    )
    retrieval_logs: Mapped[list["RetrievalLog"]] = relationship(
        back_populates="knowledge_base",
        cascade="all, delete-orphan",
    )
    evaluation_runs: Mapped[list["EvaluationRun"]] = relationship(
        back_populates="knowledge_base",
        cascade="all, delete-orphan",
    )
