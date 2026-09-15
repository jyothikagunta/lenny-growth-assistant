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

# Lightweight semantic expansion for common product/growth concepts.
# Original query terms are always preserved.
_SEARCH_EXPANSIONS = {
    "growth": (
        "growth",
        "retention",
        "activation",
        "acquisition",
        "engagement",
        "adoption",
        "scaling",
    ),
    "product": (
        "product",
        "user",
        "customer",
        "experience",
        "prioritization",
        "roadmap",
    ),
    "details": (
        "details",
        "small",
        "tiny",
        "specific",
        "concrete",
        "friction",
        "improvements",
        "iteration",
    ),
    "small": (
        "small",
        "tiny",
        "specific",
        "concrete",
        "incremental",
        "details",
    ),
    "improvement": (
        "improvement",
        "improvements",
        "iteration",
        "experiment",
        "testing",
        "optimization",
    ),
    "improvements": (
        "improvements",
        "improvement",
        "iteration",
        "experiment",
        "testing",
        "optimization",
    ),
    "user": (
        "user",
        "customer",
        "customer experience",
        "user experience",
    ),
    "customers": (
        "customers",
        "customer",
        "users",
        "user",
        "experience",
    ),
    "experience": (
        "experience",
        "user experience",
        "customer experience",
        "usability",
        "friction",
    ),
    "retention": (
        "retention",
        "churn",
        "engagement",
        "stickiness",
        "loyalty",
    ),
    "activation": (
        "activation",
        "onboarding",
        "adoption",
        "first value",
    ),
    "prioritization": (
        "prioritization",
        "prioritize",
        "tradeoffs",
        "roadmap",
        "focus",
    ),
    "leadership": (
        "leadership",
        "management",
        "teams",
        "decision making",
    ),
}


def _normalise_search_query(query: str) -> str:
    terms = re.findall(r"[\w']+", query.lower())

    meaningful_terms = [
        term
        for term in terms
        if term not in _QUESTION_FRAMING_WORDS
    ]

    if not meaningful_terms:
        return query

    # Only expand broad conceptual queries.
    # This preserves the existing exact-search behavior for normal
    # lookups and keeps the retrieval API contract stable.
    expansion_triggers = {
        "details",
        "detail",
        "small",
        "tiny",
        "improvement",
        "improvements",
        "growth",
        "experience",
        "retention",
        "activation",
        "engagement",
        "adoption",
        "friction",
    }

    if not expansion_triggers.intersection(meaningful_terms):
        return " ".join(dict.fromkeys(meaningful_terms))

    # Keep short and precise searches unchanged.
    # For example: "activation" must remain "activation".
    if len(meaningful_terms) <= 2:
        return " ".join(dict.fromkeys(meaningful_terms))

    expanded_terms = list(meaningful_terms)

    for term in meaningful_terms:
        expansion = _SEARCH_EXPANSIONS.get(term)

        if expansion:
            expanded_terms.extend(expansion)

    # Remove duplicates while preserving order.
    return " ".join(dict.fromkeys(expanded_terms))


class RetrievalServiceError(RuntimeError):
    """Raised when transcript retrieval cannot access the database."""


def search_transcripts(
    db: Session,
    query: str,
    limit: int = 5,
):
    search_query = _normalise_search_query(query)

    # Build a safe fallback using only the meaningful words from
    # the user's original query. This is important because PostgreSQL
    # websearch_to_tsquery treats space-separated terms restrictively.
    original_terms = re.findall(r"[\w']+", query.lower())

    meaningful_terms = [
        term
        for term in original_terms
        if term not in _QUESTION_FRAMING_WORDS
    ]

    fallback_query = (
        " ".join(dict.fromkeys(meaningful_terms))
        if meaningful_terms
        else query
    )

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
        # First attempt: normalized/expanded query.
        result = db.execute(
            sql,
            {
                "query": search_query,
                "limit": limit,
            },
        )

        rows = result.mappings().all()

        # If semantic expansion made the query too restrictive,
        # retry with the original meaningful terms.
        if not rows and search_query != fallback_query:
            logger.info(
                "Expanded retrieval returned no matches; "
                "retrying with original query terms",
                extra={
                    "event": "retrieval_fallback",
                    "operation": "search_transcripts",
                },
            )

            result = db.execute(
                sql,
                {
                    "query": fallback_query,
                    "limit": limit,
                },
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

        raise RetrievalServiceError(
            "Transcript retrieval is unavailable."
        ) from error

    if not rows:
        logger.info(
            "Transcript retrieval returned no matches",
            extra={
                "event": "retrieval_empty",
                "operation": "search_transcripts",
            },
        )

    return rows