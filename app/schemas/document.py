from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, field_validator


class DocumentSourceType(str, Enum):
    README = "README"
    OPENAPI = "OPENAPI"
    DATABASE_SCHEMA = "DATABASE_SCHEMA"
    DEPLOYMENT = "DEPLOYMENT"
    OTHER = "OTHER"


class DocumentStatus(str, Enum):
    DRAFT = "draft"
    ACTIVE = "active"
    ARCHIVED = "archived"


class DocumentProcessingStatus(str, Enum):
    NOT_UPLOADED = "not_uploaded"
    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class DocumentCreate(BaseModel):
    knowledge_base_id: int = Field(gt=0)
    title: str = Field(min_length=1, max_length=200, examples=["订单服务 OpenAPI 文档"])
    source_type: DocumentSourceType
    source_url: str | None = Field(default=None, max_length=500)
    content_summary: str | None = Field(default=None, max_length=5000)
    status: DocumentStatus = DocumentStatus.ACTIVE

    @field_validator("title")
    @classmethod
    def normalize_title(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("标题不能只包含空白字符")
        return value


class DocumentUpdate(BaseModel):
    knowledge_base_id: int | None = Field(default=None, gt=0)
    title: str | None = Field(default=None, min_length=1, max_length=200)
    source_type: DocumentSourceType | None = None
    source_url: str | None = Field(default=None, max_length=500)
    content_summary: str | None = Field(default=None, max_length=5000)
    status: DocumentStatus | None = None

    @field_validator("title")
    @classmethod
    def normalize_title(cls, value: str | None) -> str | None:
        if value is None:
            return value
        value = value.strip()
        if not value:
            raise ValueError("标题不能只包含空白字符")
        return value


class DocumentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    knowledge_base_id: int
    title: str
    source_type: DocumentSourceType
    source_url: str | None
    content_summary: str | None
    status: DocumentStatus
    original_filename: str | None
    file_size: int | None
    processing_status: DocumentProcessingStatus
    processing_error: str | None
    processed_at: datetime | None
    created_at: datetime
    updated_at: datetime
