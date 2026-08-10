from enum import Enum

from pydantic import BaseModel, ConfigDict

from app.schemas.timezone import BeijingDateTime


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
    created_at: BeijingDateTime
    started_at: BeijingDateTime | None
    completed_at: BeijingDateTime | None


class DocumentChunkRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    document_id: int
    chunk_index: int
    content: str
    char_start: int
    char_end: int
    created_at: BeijingDateTime
