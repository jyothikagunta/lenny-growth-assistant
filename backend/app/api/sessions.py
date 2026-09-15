import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

from app.db.database import get_db
from app.models.session import Session as SessionModel
from app.schemas.session import SessionCreate, SessionResponse


router = APIRouter(
    prefix="/sessions",
    tags=["Sessions"],
)
logger = logging.getLogger(__name__)


@router.post(
    "",
    response_model=SessionResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_session(
    payload: SessionCreate,
    db: Session = Depends(get_db),
):
    session = SessionModel(
        user_id=payload.user_id,
    )

    try:
        db.add(session)
        db.commit()
        db.refresh(session)
    except SQLAlchemyError as error:
        db.rollback()
        logger.error(
            "Session persistence failed",
            extra={
                "event": "database_failure",
                "operation": "create_session",
                "error_type": type(error).__name__,
            },
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="The session could not be created. Please try again.",
        ) from error

    return session


@router.get(
    "/{session_id}",
    response_model=SessionResponse,
)
def get_session(
    session_id: UUID,
    db: Session = Depends(get_db),
):
    try:
        session = (
            db.query(SessionModel)
            .filter(SessionModel.id == session_id)
            .first()
        )
    except SQLAlchemyError as error:
        logger.error(
            "Session lookup failed",
            extra={
                "event": "database_failure",
                "session_id": session_id,
                "operation": "get_session",
                "error_type": type(error).__name__,
            },
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="The database is temporarily unavailable. Please try again.",
        ) from error

    if session is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found",
        )

    return session