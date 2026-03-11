"""Session service — chat session lifecycle and title generation."""

import logging
import re
import uuid
from datetime import UTC, datetime

from app.repo import chat_completion
from app.repo.session_store import (
    add_message,
    create_session,
    delete_session,
    get_messages,
    get_session,
    list_sessions,
    update_session_title,
    update_session_ts,
)
from app.types import ChatSession

logger = logging.getLogger(__name__)

_TITLE_PROMPT = """Generate a short (4-6 word) title for this chat conversation
based on the user's first message. Be concise and descriptive.
Respond with just the title, no quotes or extra formatting."""


def new_session() -> ChatSession:
    """Create a new chat session with a placeholder title."""
    sid = str(uuid.uuid4())
    now = datetime.now(UTC).isoformat()
    create_session(sid, "New conversation", now)
    return ChatSession(
        session_id=sid, title="New conversation",
        created_at=now, updated_at=now, message_count=0,
    )


def generate_title(session_id: str, first_message: str) -> str:
    """Auto-generate a session title from the first user message."""
    try:
        raw = chat_completion(
            system_prompt=_TITLE_PROMPT,
            user_message=first_message,
            temperature=0.3,
        )
        title = raw.strip().strip('"').strip("'")[:80]
        # Strip markdown fences if the model wraps it
        title = re.sub(r"^```.*\n?", "", title)
        title = re.sub(r"\n?```$", "", title)
        if title:
            update_session_title(session_id, title)
            logger.info("Session %s titled: %s", session_id[:8], title)
            return title
    except Exception:
        logger.warning("Title generation failed for session %s", session_id[:8])
    return "New conversation"


def get_all_sessions(limit: int = 50) -> list[ChatSession]:
    """List all chat sessions, newest first."""
    rows = list_sessions(limit=limit)
    return [ChatSession(**r) for r in rows]


def get_session_detail(session_id: str) -> dict | None:
    """Get session metadata + messages."""
    session = get_session(session_id)
    if not session:
        return None
    messages = get_messages(session_id)
    return {"session": ChatSession(**{**session, "message_count": len(messages)}), "messages": messages}


def remove_session(session_id: str) -> bool:
    """Delete a session. Returns True if it existed."""
    if not get_session(session_id):
        return False
    delete_session(session_id)
    return True


def store_message(
    session_id: str, role: str, content: str,
    citations: list | None = None,
    retrieval_metadata: dict | None = None,
) -> None:
    """Persist a message and bump session timestamp."""
    now = datetime.now(UTC).isoformat()
    add_message(session_id, role, content, citations, retrieval_metadata, now)
    update_session_ts(session_id, now)
