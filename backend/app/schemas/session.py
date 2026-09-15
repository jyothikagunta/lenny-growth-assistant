from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class SessionCreate(BaseModel):
    user_id: str | None = Field(default=None, max_length=255)


class SessionResponse(BaseModel):
    id: UUID
    user_id: str | None
    created_at: datetime

    model_config = {"from_attributes": True}