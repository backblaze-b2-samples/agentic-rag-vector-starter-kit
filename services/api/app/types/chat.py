"""Types for chat and conversation management."""

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel


class MessageRole(StrEnum):
    user = "user"
    assistant = "assistant"
    system = "system"


class Citation(BaseModel):
    """A reference to a source document chunk used in a response."""
    index: int  # [1], [2], etc.
    doc_id: str
    doc_title: str
    section_path: str
    source_filename: str
    page: int | None = None
    chunk_text: str  # relevant excerpt
    download_url: str | None = None


class ChatMessage(BaseModel):
    """A single message in a conversation."""
    role: MessageRole
    content: str
    citations: list[Citation] = []
    timestamp: datetime | None = None


class ChatRequest(BaseModel):
    """Incoming chat request from the frontend."""
    message: str
    conversation_id: str | None = None  # deprecated alias for session_id
    session_id: str | None = None  # None = new session


class ChatResponse(BaseModel):
    """Full chat response with citations."""
    conversation_id: str
    message: ChatMessage
    retrieval_metadata: "RetrievalInfo | None" = None


class RetrievalInfo(BaseModel):
    """Metadata about the retrieval process, for transparency."""
    route: str  # kb_only, no_retrieval, etc.
    queries_generated: int
    candidates_found: int
    evidence_used: int
    retrieval_loops: int
    latency_ms: float
