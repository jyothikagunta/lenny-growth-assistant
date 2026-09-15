import logging
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.services.agent import (
    AgentConfigurationError,
    SYSTEM_PROMPT,
    generate_grounded_answer,
)
from app.services.llm import LLMConfigurationError, LLMServiceError
from app.services.retrieval import RetrievalServiceError
from app.services.citations import (
    ensure_grounding_acknowledgement,
    resolve_source_references,
)
from app.models.message import Message
from app.models.session import Session as SessionModel

RECENT_MESSAGE_LIMIT = 10
logger = logging.getLogger(__name__)

SAFE_SERVICE_ERROR = "The assistant is temporarily unavailable. Please try again."
SAFE_CONFIGURATION_ERROR = "The assistant is not configured for requests right now."
SAFE_DATABASE_ERROR = "The conversation could not be saved. Please try again."


def build_history(messages) -> str:
    if not messages:
        return "No previous conversation history."

    return "\n".join(
        f"{message.role.upper()}: {message.content}"
        for message in messages
    )


def chat_with_transcripts(
    db: Session,
    session_id: UUID,
    query: str,
    limit: int = 5,
) -> dict:
    try:
        session = (
            db.query(SessionModel)
            .filter(SessionModel.id == session_id)
            .first()
        )
    except SQLAlchemyError as error:
        logger.error(
            "Database session lookup failed",
            extra={
                "event": "database_failure",
                "session_id": session_id,
                "operation": "session_lookup",
                "error_type": type(error).__name__,
            },
        )
        raise HTTPException(status_code=503, detail=SAFE_DATABASE_ERROR) from error

    if session is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found",
        )

    try:
        previous_messages = (
            db.query(Message)
            .filter(Message.session_id == session_id)
            .order_by(Message.created_at.desc())
            .limit(RECENT_MESSAGE_LIMIT)
            .all()
        )
    except SQLAlchemyError as error:
        logger.error(
            "Database history lookup failed",
            extra={
                "event": "database_failure",
                "session_id": session_id,
                "operation": "history_lookup",
                "error_type": type(error).__name__,
            },
        )
        raise HTTPException(status_code=503, detail=SAFE_DATABASE_ERROR) from error
    previous_messages.reverse()

    user_message = Message(
        session_id=session_id,
        role="user",
        content=query,
    )
    try:
        db.add(user_message)
        db.commit()
    except SQLAlchemyError as error:
        db.rollback()
        logger.error(
            "Database user message persistence failed",
            extra={
                "event": "database_failure",
                "session_id": session_id,
                "operation": "persist_user_message",
                "error_type": type(error).__name__,
            },
        )
        raise HTTPException(status_code=503, detail=SAFE_DATABASE_ERROR) from error

    history = build_history(previous_messages)
    try:
        agent_response = generate_grounded_answer(
            db=db,
            query=query,
            history=history,
            limit=limit,
        )
    except (AgentConfigurationError, LLMConfigurationError) as error:
        raise HTTPException(status_code=503, detail=SAFE_CONFIGURATION_ERROR) from error
    except (LLMServiceError, RetrievalServiceError) as error:
        raise HTTPException(status_code=503, detail=SAFE_SERVICE_ERROR) from error

    answer = agent_response.answer
    results = agent_response.results
    sources = resolve_source_references(answer, results)
    if results:
        answer = ensure_grounding_acknowledgement(answer, sources)

    assistant_message = Message(
        session_id=session_id,
        role="assistant",
        content=answer,
    )
    try:
        db.add(assistant_message)
        db.commit()
    except SQLAlchemyError as error:
        db.rollback()
        logger.error(
            "Database assistant message persistence failed",
            extra={
                "event": "database_failure",
                "session_id": session_id,
                "operation": "persist_assistant_message",
                "error_type": type(error).__name__,
            },
        )
        raise HTTPException(status_code=503, detail=SAFE_DATABASE_ERROR) from error

    return {
        "session_id": session_id,
        "answer": answer,
        "sources": sources,
        "artifact": agent_response.artifact,
    }