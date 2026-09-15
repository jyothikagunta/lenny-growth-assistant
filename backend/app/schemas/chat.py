from uuid import UUID

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    session_id: UUID
    query: str = Field(min_length=1, max_length=5000)
    limit: int = Field(default=5, ge=1, le=10)


class ChatSource(BaseModel):
    episode_title: str
    guest_name: str | None
    source_url: str | None


class ArtifactResponse(BaseModel):
    artifact_type: str
    title: str
    content: str
    sources: list[ChatSource]
    is_untrusted: bool = True

    model_config = {"from_attributes": True}


class ChatResponse(BaseModel):
    session_id: UUID
    answer: str
    sources: list[ChatSource]
    artifact: ArtifactResponse | None = None