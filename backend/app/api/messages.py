import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

from app.db.database import get_db
from app.models.message import Message
from app.models.session import Session as SessionModel
from app.schemas.message import MessageCreate, MessageResponse


router = APIRouter(
    prefix="/sessions",
    tags=["Messages"],
)
logger = logging.getLogger(__name__)


@router.post(
    "/{session_id}/messages",
    response_model=MessageResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_message(
    session_id: UUID,
    payload: MessageCreate,
    db: Session = Depends(get_db),
):
    # Make sure the session exists.
    try:
        session = (
            db.query(SessionModel)
            .filter(SessionModel.id == session_id)
            .first()
        )
    except SQLAlchemyError as error:
        logger.error(
            "Message session lookup failed",
            extra={
                "event": "database_failure",
                "session_id": session_id,
                "operation": "message_session_lookup",
                "error_type": type(error).__name__,
            },
        )
        raise HTTPException(status_code=503, detail="The database is temporarily unavailable. Please try again.") from error

    if session is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found",
        )

    message = Message(
        session_id=session_id,
        role="user",
        content=payload.content,
    )

    try:
        db.add(message)
        db.commit()
        db.refresh(message)
    except SQLAlchemyError as error:
        db.rollback()
        logger.error(
            "Message persistence failed",
            extra={
                "event": "database_failure",
                "session_id": session_id,
                "operation": "create_message",
                "error_type": type(error).__name__,
            },
        )
        raise HTTPException(status_code=503, detail="The message could not be saved. Please try again.") from error

    return message


@router.get(
    "/{session_id}/messages",
    response_model=list[MessageResponse],
)
def get_messages(
    session_id: UUID,
    db: Session = Depends(get_db),
):
    # Make sure the session exists.
    try:
        session = (
            db.query(SessionModel)
            .filter(SessionModel.id == session_id)
            .first()
        )
    except SQLAlchemyError as error:
        logger.error(
            "Message history session lookup failed",
            extra={
                "event": "database_failure",
                "session_id": session_id,
                "operation": "message_history_session_lookup",
                "error_type": type(error).__name__,
            },
        )
        raise HTTPException(status_code=503, detail="The database is temporarily unavailable. Please try again.") from error

    if session is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found",
        )

    try:
        messages = (
            db.query(Message)
            .filter(Message.session_id == session_id)
            .order_by(Message.created_at.asc())
            .all()
        )
    except SQLAlchemyError as error:
        logger.error(
            "Message history lookup failed",
            extra={
                "event": "database_failure",
                "session_id": session_id,
                "operation": "get_messages",
                "error_type": type(error).__name__,
            },
        )
        raise HTTPException(status_code=503, detail="The database is temporarily unavailable. Please try again.") from error

    return messages