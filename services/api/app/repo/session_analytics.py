"""Session-level analytics — joins sessions, messages, and query metrics.

Provides aggregated RAGAS scores and per-message evaluation data
for the dashboard session drill-down views.
"""

import json
import logging

from app.repo.query_log import _exec_read, _init_db

logger = logging.getLogger(__name__)


def get_sessions_with_ragas(limit: int = 20, offset: int = 0) -> list[dict]:
    """List sessions with aggregated RAGAS scores and query counts.

    Joins chat_sessions with queries table (via session_id) to compute
    average faithfulness, context_precision, and latency per session.
    """
    _init_db()
    rows = _exec_read(
        """SELECT
             s.session_id, s.title, s.created_at, s.updated_at,
             (SELECT COUNT(*) FROM chat_messages WHERE session_id = s.session_id) AS message_count,
             AVG(q.faithfulness) AS avg_faithfulness,
             AVG(q.context_precision) AS avg_context_precision,
             AVG(q.latency_ms) AS avg_latency_ms,
             COUNT(q.id) AS total_queries
           FROM chat_sessions s
           LEFT JOIN queries q ON q.session_id = s.session_id
           GROUP BY s.session_id
           ORDER BY s.updated_at DESC
           LIMIT ? OFFSET ?""",
        (limit, offset),
    )
    results = []
    for r in rows:
        results.append({
            "session_id": r["session_id"],
            "title": r["title"],
            "created_at": r["created_at"],
            "updated_at": r["updated_at"],
            "message_count": r["message_count"],
            "avg_faithfulness": round(r["avg_faithfulness"], 3) if r["avg_faithfulness"] else None,
            "avg_context_precision": round(r["avg_context_precision"], 3) if r["avg_context_precision"] else None,
            "avg_latency_ms": round(r["avg_latency_ms"], 1) if r["avg_latency_ms"] else None,
            "total_queries": r["total_queries"],
        })
    return results


def get_session_messages_with_eval(session_id: str) -> list[dict]:
    """Get all messages in a session with per-message RAGAS scores.

    For assistant messages, joins with the queries table to pull
    faithfulness, context_precision, route, latency, and evidence count.
    """
    _init_db()
    rows = _exec_read(
        """SELECT
             m.id, m.role, m.content, m.citations, m.retrieval_metadata, m.timestamp,
             q.faithfulness, q.context_precision, q.route, q.latency_ms,
             q.evidence_count
           FROM chat_messages m
           LEFT JOIN queries q ON q.session_id = m.session_id AND q.query = (
             SELECT cm.content FROM chat_messages cm
             WHERE cm.session_id = m.session_id AND cm.role = 'user'
               AND cm.id < m.id ORDER BY cm.id DESC LIMIT 1
           ) AND m.role = 'assistant'
           WHERE m.session_id = ?
           ORDER BY m.id""",
        (session_id,),
    )
    results = []
    for r in rows:
        msg = {
            "id": r["id"],
            "role": r["role"],
            "content": r["content"],
            "timestamp": r["timestamp"],
            "citations": json.loads(r["citations"]) if r["citations"] else [],
            "faithfulness": r["faithfulness"],
            "context_precision": r["context_precision"],
            "route": r["route"],
            "latency_ms": r["latency_ms"],
            "evidence_count": r["evidence_count"],
        }
        # Parse retrieval_metadata if present
        if r["retrieval_metadata"]:
            try:
                msg["retrieval_metadata"] = json.loads(r["retrieval_metadata"])
            except (json.JSONDecodeError, TypeError):
                msg["retrieval_metadata"] = None
        else:
            msg["retrieval_metadata"] = None
        results.append(msg)
    return results
