from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.schemas.search import SearchRequest, SearchResult
from app.services.retrieval import search_transcripts


router = APIRouter(
    prefix="/search",
    tags=["Search"],
)


@router.post(
    "",
    response_model=list[SearchResult],
)
def search(
    payload: SearchRequest,
    db: Session = Depends(get_db),
):
    results = search_transcripts(
        db=db,
        query=payload.query,
        limit=payload.limit,
    )

    return [
        SearchResult(
            chunk_id=result["chunk_id"],
            transcript_id=result["transcript_id"],
            episode_title=result["episode_title"],
            guest_name=result["guest_name"],
            source_url=result["source_url"],
            content=result["content"],
            rank=float(result["rank"]),
        )
        for result in results
    ]