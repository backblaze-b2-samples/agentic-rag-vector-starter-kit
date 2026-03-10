"""Chat endpoints — send messages, get history, stream responses."""

import logging

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from app.service.chat import get_conversation, handle_chat, handle_chat_stream
from app.types import ChatRequest, ChatResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/chat", tags=["chat"])


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
        """Wrap stream generator to emit error event on failure."""
        try:
            yield from handle_chat_stream(request)
        except Exception:
            logger.exception("Stream failed")
            yield 'data: {"type": "error", "detail": "Stream interrupted"}\n\n'

    return StreamingResponse(
        safe_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/history/{conversation_id}")
async def chat_history(conversation_id: str):
    """Get conversation history by ID."""
    history = get_conversation(conversation_id)
    if not history:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return {
        "conversation_id": conversation_id,
        "messages": [m.model_dump() for m in history],
        "count": len(history),
    }
