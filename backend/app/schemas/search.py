from uuid import UUID

from pydantic import BaseModel, Field


class SearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=1000)
    limit: int = Field(default=5, ge=1, le=20)


class SearchResult(BaseModel):
    chunk_id: UUID
    transcript_id: UUID
    episode_title: str
    guest_name: str | None
    source_url: str | None
    content: str
    rank: float