"""Session store — SQLite persistence for chat sessions and messages.

Uses the same database file as query_log.py.
"""

import json
import logging
import sqlite3
from pathlib import Path
from threading import Lock

logger = logging.getLogger(__name__)

_DB_PATH = Path(__file__).parent.parent.parent / "data" / "query_log.sqlite"
_write_lock = Lock()
_initialized = False

_SESSIONS_SCHEMA = """
CREATE TABLE IF NOT EXISTS chat_sessions (
    session_id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
)
"""

_MESSAGES_SCHEMA = """
CREATE TABLE IF NOT EXISTS chat_messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    citations TEXT DEFAULT '[]',
    retrieval_metadata TEXT,
    timestamp TEXT NOT NULL,
    FOREIGN KEY (session_id) REFERENCES chat_sessions(session_id)
)
"""


def _get_conn() -> sqlite3.Connection:
    _DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(_DB_PATH), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def _init_db() -> None:
    global _initialized
    if _initialized:
        return
    conn = _get_conn()
    try:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute(_SESSIONS_SCHEMA)
        conn.execute(_MESSAGES_SCHEMA)
        conn.commit()
        _initialized = True
    finally:
        conn.close()


def _exec_write(sql: str, params: tuple = ()) -> None:
    _init_db()
    with _write_lock:
        conn = _get_conn()
        try:
            conn.execute(sql, params)
            conn.commit()
        finally:
            conn.close()


def _exec_read(sql: str, params: tuple = ()) -> list[dict]:
    _init_db()
    conn = _get_conn()
    try:
        rows = conn.execute(sql, params).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def create_session(session_id: str, title: str, created_at: str) -> None:
    """Create a new chat session."""
    _exec_write(
        "INSERT INTO chat_sessions (session_id, title, created_at, updated_at) VALUES (?, ?, ?, ?)",
        (session_id, title, created_at, created_at),
    )


def update_session_title(session_id: str, title: str) -> None:
    """Update the title of a session (e.g. after auto-generation)."""
    _exec_write(
        "UPDATE chat_sessions SET title = ? WHERE session_id = ?",
        (title, session_id),
    )


def update_session_ts(session_id: str, updated_at: str) -> None:
    """Bump the updated_at timestamp."""
    _exec_write(
        "UPDATE chat_sessions SET updated_at = ? WHERE session_id = ?",
        (updated_at, session_id),
    )


def list_sessions(limit: int = 50) -> list[dict]:
    """List sessions with message counts, newest first."""
    return _exec_read(
        """SELECT s.session_id, s.title, s.created_at, s.updated_at,
                  COUNT(m.id) AS message_count
           FROM chat_sessions s
           LEFT JOIN chat_messages m ON m.session_id = s.session_id
           GROUP BY s.session_id
           ORDER BY s.updated_at DESC
           LIMIT ?""",
        (limit,),
    )


def get_session(session_id: str) -> dict | None:
    """Get a single session by ID."""
    rows = _exec_read(
        "SELECT * FROM chat_sessions WHERE session_id = ?", (session_id,),
    )
    return rows[0] if rows else None


def delete_session(session_id: str) -> None:
    """Delete a session and all its messages."""
    _init_db()
    with _write_lock:
        conn = _get_conn()
        try:
            conn.execute("DELETE FROM chat_messages WHERE session_id = ?", (session_id,))
            conn.execute("DELETE FROM chat_sessions WHERE session_id = ?", (session_id,))
            conn.commit()
        finally:
            conn.close()


def add_message(
    session_id: str, role: str, content: str,
    citations: list | None = None,
    retrieval_metadata: dict | None = None,
    timestamp: str = "",
) -> None:
    """Add a message to a session."""
    _exec_write(
        """INSERT INTO chat_messages
           (session_id, role, content, citations, retrieval_metadata, timestamp)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (
            session_id, role, content,
            json.dumps(citations or []),
            json.dumps(retrieval_metadata) if retrieval_metadata else None,
            timestamp,
        ),
    )


def get_messages(session_id: str) -> list[dict]:
    """Get all messages for a session, ordered by ID."""
    rows = _exec_read(
        "SELECT * FROM chat_messages WHERE session_id = ? ORDER BY id",
        (session_id,),
    )
    for r in rows:
        r["citations"] = json.loads(r.get("citations") or "[]")
        r["retrieval_metadata"] = (
            json.loads(r["retrieval_metadata"]) if r.get("retrieval_metadata") else None
        )
    return rows
