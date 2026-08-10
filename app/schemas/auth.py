from pydantic import BaseModel, ConfigDict

from app.schemas.timezone import BeijingDateTime


class TokenRead(BaseModel):
    access_token: str
    token_type: str = "bearer"


class CurrentUserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    is_admin: bool
    created_at: BeijingDateTime
