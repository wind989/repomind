from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.core.timezone import beijing_now

if TYPE_CHECKING:
    from app.models.document_chunk import DocumentChunk
    from app.models.document_processing_task import DocumentProcessingTask
    from app.models.knowledge_base import KnowledgeBase


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[int] = mapped_column(primary_key=True)
    knowledge_base_id: Mapped[int] = mapped_column(
        ForeignKey("knowledge_bases.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    source_type: Mapped[str] = mapped_column(String(30), nullable=False)
    source_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    content_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(20), server_default="active", nullable=False)
    original_filename: Mapped[str | None] = mapped_column(String(255), nullable=True)
    storage_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    file_size: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    processing_status: Mapped[str] = mapped_column(
        String(20),
        server_default="not_uploaded",
        nullable=False,
    )
    processing_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=beijing_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=beijing_now,
        onupdate=beijing_now,
        nullable=False,
    )

    knowledge_base: Mapped["KnowledgeBase"] = relationship(back_populates="documents")
    chunks: Mapped[list["DocumentChunk"]] = relationship(
        back_populates="document",
        cascade="all, delete-orphan",
    )
    processing_tasks: Mapped[list["DocumentProcessingTask"]] = relationship(
        back_populates="document",
        cascade="all, delete-orphan",
    )
