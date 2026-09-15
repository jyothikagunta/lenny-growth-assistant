from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from uuid import UUID

from app.db.database import get_db
from app.services.chat import chat_with_transcripts


router = APIRouter(prefix="/chat", tags=["Chat"])


class ChatRequest(BaseModel):
    session_id: UUID
    query: str = Field(min_length=1, max_length=5000)
    limit: int = Field(ge=1, le=10)


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


@router.post("", response_model=ChatResponse)
def chat(
    payload: ChatRequest,
    db: Session = Depends(get_db),
):
    return chat_with_transcripts(
        db=db,
        session_id=payload.session_id,
        query=payload.query,
        limit=payload.limit,
    )