"""Chat endpoints — sessions, messages, and streaming responses."""

import logging

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from app.service.chat import handle_chat, handle_chat_stream
from app.service.sessions import get_all_sessions, get_session_detail, new_session, remove_session
from app.types import ChatRequest, ChatResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/chat", tags=["chat"])


# --- Session endpoints ---

@router.get("/sessions")
async def list_sessions(limit: int = 50):
    """List all chat sessions, newest first."""
    sessions = get_all_sessions(limit=limit)
    return [s.model_dump() for s in sessions]


@router.post("/sessions")
async def create_session():
    """Create a new empty chat session."""
    session = new_session()
    return session.model_dump()


@router.get("/sessions/{session_id}")
async def get_session(session_id: str):
    """Get session metadata + messages."""
    detail = get_session_detail(session_id)
    if not detail:
        raise HTTPException(status_code=404, detail="Session not found")
    return {
        "session": detail["session"].model_dump(),
        "messages": detail["messages"],
    }


@router.delete("/sessions/{session_id}")
async def delete_session(session_id: str):
    """Delete a chat session and its messages."""
    if not remove_session(session_id):
        raise HTTPException(status_code=404, detail="Session not found")
    return {"deleted": True}


# --- Chat message endpoints ---

@router.post("", response_model=ChatResponse)
async def send_message(request: ChatRequest):
    """Send a chat message and get a grounded response with citations."""
    if not request.message.strip():
        raise HTTPException(status_code=400, detail="Message required")
    try:
        return handle_chat(request)
    except Exception:
        logger.exception("Chat handler failed")
        raise HTTPException(status_code=503, detail="Chat service unavailable") from None


@router.post("/stream")
async def stream_message(request: ChatRequest):
    """Stream a chat response via Server-Sent Events."""
    if not request.message.strip():
        raise HTTPException(status_code=400, detail="Message required")

    def safe_stream():
        try:
            yield from handle_chat_stream(request)
        except Exception:
            logger.exception("Stream failed")
            yield 'data: {"type": "error", "detail": "Stream interrupted"}\n\n'

    return StreamingResponse(
        safe_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"},
    )


@router.get("/history/{conversation_id}")
async def chat_history(conversation_id: str):
    """Get conversation history by ID (backward compat, delegates to session)."""
    detail = get_session_detail(conversation_id)
    if not detail:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return {
        "conversation_id": conversation_id,
        "messages": detail["messages"],
        "count": len(detail["messages"]),
    }
