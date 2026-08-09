from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict


class DocumentProcessingTaskOperation(str, Enum):
    UPLOAD = "upload"
    REPROCESS = "reprocess"


class DocumentProcessingTaskStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class DocumentProcessingTaskRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    document_id: int
    operation: DocumentProcessingTaskOperation
    status: DocumentProcessingTaskStatus
    error_message: str | None
    created_at: datetime
    started_at: datetime | None
    completed_at: datetime | None


class DocumentChunkRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    document_id: int
    chunk_index: int
    content: str
    char_start: int
    char_end: int
    created_at: datetime
