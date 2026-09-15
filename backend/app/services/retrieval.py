import logging
import re

from sqlalchemy import text
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

_QUESTION_FRAMING_WORDS = {
    "about",
    "are",
    "be",
    "being",
    "discussed",
    "does",
    "did",
    "do",
    "episode",
    "how",
    "in",
    "is",
    "of",
    "the",
    "this",
    "what",
    "were",
    "which",
    "who",
}


def _normalise_search_query(query: str) -> str:
    terms = re.findall(r"[\w']+", query.lower())
    meaningful_terms = [
        term for term in terms if term not in _QUESTION_FRAMING_WORDS
    ]
    return " ".join(meaningful_terms) or query


class RetrievalServiceError(RuntimeError):
    """Raised when transcript retrieval cannot access the database."""


def search_transcripts(
    db: Session,
    query: str,
    limit: int = 5,
):
    search_query = _normalise_search_query(query)
    logger.info(
        "Transcript retrieval started",
        extra={
            "event": "retrieval_start",
            "operation": "search_transcripts",
        },
    )
    sql = text(
        """
        SELECT
            tc.id AS chunk_id,
            tc.transcript_id,
            t.episode_title,
            t.guest_name,
            t.source_url,
            tc.content,
            ts_rank(
                to_tsvector('english', tc.content),
                websearch_to_tsquery('english', :query)
            ) AS rank
        FROM transcript_chunks tc
        JOIN transcripts t
            ON t.id = tc.transcript_id
        WHERE to_tsvector('english', tc.content)
              @@ websearch_to_tsquery('english', :query)
        ORDER BY rank DESC
        LIMIT :limit
        """
    )

    try:
        result = db.execute(
            sql,
            {"query": search_query, "limit": limit},
        )
        rows = result.mappings().all()
    except Exception as error:
        logger.error(
            "Transcript retrieval failed",
            extra={
                "event": "retrieval_failure",
                "operation": "search_transcripts",
                "error_type": type(error).__name__,
            },
        )
        raise RetrievalServiceError("Transcript retrieval is unavailable.") from error

    if not rows:
        logger.info(
            "Transcript retrieval returned no matches",
            extra={
                "event": "retrieval_empty",
                "operation": "search_transcripts",
            },
        )
    return rows