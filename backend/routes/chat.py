from fastapi import APIRouter, Depends, Path, status
from sqlalchemy.orm import Session

from controllers.chat import (
    clear_chat_history,
    get_chat_history,
    list_user_chat_sessions,
    process_chat_message,
)
from database import get_db
from middleware.auth import get_current_user
from schemas.chat import (
    ChatRequest,
    ChatResponse,
    ChatSessionHistoryResponse,
    ChatSessionSummary,
)

router = APIRouter(prefix="/chat", tags=["AI Tax Chat Assistant"])


@router.post(
    "",
    response_model=ChatResponse,
    status_code=status.HTTP_200_OK,
    summary="Send a message to the AI Tax Assistant",
    description=(
        "Processes user query for Indian Income Tax filing, regime comparisons, "
        "deductions (80C, 80D, HRA), and Form 16/26AS reconciliation with conversational context."
    ),
)
def send_chat_message(
    request: ChatRequest,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Execute AI tax assistant query with multi-turn conversation support and database persistence.
    Requires Bearer JWT authentication.
    """
    return process_chat_message(
        db=db,
        user_id=current_user["id"],
        request=request,
    )


@router.get(
    "/sessions",
    response_model=list[ChatSessionSummary],
    summary="List all user chat sessions",
    description="Retrieve a list of past conversation sessions with message counts and last message previews.",
)
def get_user_sessions(
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Fetch all active chat sessions belonging to the authenticated user."""
    return list_user_chat_sessions(
        db=db,
        user_id=current_user["id"],
    )


@router.get(
    "/history/{session_id}",
    response_model=ChatSessionHistoryResponse,
    summary="Retrieve full conversation history",
    description="Load previous messages exchanged within a specific chat session.",
)
def get_session_history(
    session_id: str = Path(..., description="Unique UUID of the chat session"),
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Retrieve full chronological conversation thread for a given session."""
    return get_chat_history(
        db=db,
        session_id=session_id,
        user_id=current_user["id"],
    )


@router.delete(
    "/history/{session_id}",
    summary="Clear conversation history",
    description="Permanently delete all messages associated with a specific chat session.",
)
def delete_session(
    session_id: str = Path(..., description="Unique UUID of the chat session to delete"),
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Clear chat history for the specified session."""
    return clear_chat_history(
        db=db,
        session_id=session_id,
        user_id=current_user["id"],
    )
