from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas.timezone import BeijingDateTime


class KnowledgeBaseCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100, examples=["订单服务资料"])
    description: str | None = Field(default=None, max_length=2000, examples=["订单服务的接口和部署资料"])

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("名称不能只包含空白字符")
        return value


class KnowledgeBaseUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=2000)

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str | None) -> str | None:
        if value is None:
            return value
        value = value.strip()
        if not value:
            raise ValueError("名称不能只包含空白字符")
        return value


class KnowledgeBaseRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    description: str | None
    created_at: BeijingDateTime
    updated_at: BeijingDateTime
