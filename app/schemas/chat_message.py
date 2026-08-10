from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas.timezone import BeijingDateTime


class ChatRole(str, Enum):
    USER = "user"
    ASSISTANT = "assistant"


class ChatMessageCreate(BaseModel):
    knowledge_base_id: int = Field(gt=0)
    role: ChatRole
    content: str = Field(min_length=1, max_length=10000, examples=["创建订单接口需要哪些参数？"])

    @field_validator("content")
    @classmethod
    def normalize_content(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("内容不能只包含空白字符")
        return value


class ChatMessageRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    knowledge_base_id: int
    role: ChatRole
    content: str
    created_at: BeijingDateTime
