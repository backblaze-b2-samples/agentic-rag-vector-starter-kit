"""Types for chat session management."""

from pydantic import BaseModel


class ChatSession(BaseModel):
    """A chat session with title and metadata."""
    session_id: str
    title: str
    created_at: str
    updated_at: str
    message_count: int = 0


class ChatSessionMessage(BaseModel):
    """A persisted chat message within a session."""
    id: int
    session_id: str
    role: str
    content: str
    citations: list = []
    retrieval_metadata: dict | None = None
    timestamp: str
