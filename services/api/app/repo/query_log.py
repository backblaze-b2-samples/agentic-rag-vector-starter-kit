"""Query and ingestion log — SQLite persistence for dashboard metrics.

Stores one record per chat query and one per document ingestion.
All sqlite3 usage is confined to this module.
"""

import json
import logging
import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path
from threading import Lock

logger = logging.getLogger(__name__)

_DB_PATH = Path(__file__).parent.parent.parent / "data" / "query_log.sqlite"
_write_lock = Lock()
_initialized = False

_QUERIES_SCHEMA = """
CREATE TABLE IF NOT EXISTS queries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts TEXT NOT NULL, query TEXT NOT NULL, route TEXT NOT NULL,
    queries_generated INTEGER NOT NULL, total_candidates INTEGER NOT NULL,
    post_fusion_candidates INTEGER NOT NULL, post_rerank_count INTEGER NOT NULL,
    evidence_count INTEGER NOT NULL, retrieval_loops INTEGER NOT NULL,
    latency_ms REAL NOT NULL, top1_score REAL, top5_scores TEXT,
    is_sufficient INTEGER NOT NULL
)
"""

_INGESTIONS_SCHEMA = """
CREATE TABLE IF NOT EXISTS ingestions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts TEXT NOT NULL, doc_id TEXT NOT NULL, filename TEXT NOT NULL,
    status TEXT NOT NULL, chunk_count INTEGER NOT NULL,
    total_tokens INTEGER NOT NULL, classification TEXT NOT NULL,
    error_message TEXT
)
"""


def _get_conn() -> sqlite3.Connection:
    """Open a new SQLite connection. Caller must close it."""
    _DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(_DB_PATH), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def _init_db() -> None:
    """Create tables if they don't exist (idempotent)."""
    global _initialized
    if _initialized:
        return
    conn = _get_conn()
    try:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute(_QUERIES_SCHEMA)
        conn.execute(_INGESTIONS_SCHEMA)
        conn.commit()
        _initialized = True
    finally:
        conn.close()


def _exec_write(sql: str, params: tuple) -> None:
    """Execute a single INSERT under the write lock."""
    _init_db()
    with _write_lock:
        conn = _get_conn()
        try:
            conn.execute(sql, params)
            conn.commit()
        finally:
            conn.close()


def _exec_read(sql: str, params: tuple = ()) -> list[sqlite3.Row]:
    """Execute a read query and return all rows."""
    _init_db()
    conn = _get_conn()
    try:
        return conn.execute(sql, params).fetchall()
    finally:
        conn.close()


def log_query(
    query: str, route: str, queries_generated: int, total_candidates: int,
    post_fusion_candidates: int, post_rerank_count: int, evidence_count: int,
    retrieval_loops: int, latency_ms: float, top1_score: float | None,
    top5_scores: list[float], is_sufficient: bool,
) -> None:
    """Insert a query log record."""
    _exec_write(
        """INSERT INTO queries
           (ts, query, route, queries_generated, total_candidates,
            post_fusion_candidates, post_rerank_count, evidence_count,
            retrieval_loops, latency_ms, top1_score, top5_scores, is_sufficient)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (datetime.now(UTC).isoformat(), query, route, queries_generated,
         total_candidates, post_fusion_candidates, post_rerank_count,
         evidence_count, retrieval_loops, latency_ms, top1_score,
         json.dumps(top5_scores), 1 if is_sufficient else 0),
    )


def log_ingestion(
    doc_id: str, filename: str, status: str, chunk_count: int,
    total_tokens: int, classification: str, error_message: str | None,
) -> None:
    """Insert an ingestion log record."""
    _exec_write(
        """INSERT INTO ingestions
           (ts, doc_id, filename, status, chunk_count,
            total_tokens, classification, error_message)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (datetime.now(UTC).isoformat(), doc_id, filename, status,
         chunk_count, total_tokens, classification, error_message),
    )


def get_recent_queries(limit: int = 20) -> list[dict]:
    """Return the most recent query log entries."""
    rows = _exec_read(
        """SELECT id, ts, query, route, queries_generated, total_candidates,
                  evidence_count, retrieval_loops, latency_ms, top1_score,
                  is_sufficient
           FROM queries ORDER BY id DESC LIMIT ?""", (limit,),
    )
    return [{**dict(r), "is_sufficient": bool(r["is_sufficient"])} for r in rows]


def get_recent_ingestions(limit: int = 20) -> list[dict]:
    """Return the most recent ingestion log entries."""
    rows = _exec_read(
        """SELECT id, ts, doc_id, filename, status, chunk_count,
                  total_tokens, classification, error_message
           FROM ingestions ORDER BY id DESC LIMIT ?""", (limit,),
    )
    return [dict(r) for r in rows]


def get_query_stats(days: int = 7) -> dict:
    """Aggregate query stats over a time window."""
    all_rows = _exec_read("SELECT latency_ms, top1_score, route FROM queries")
    total = len(all_rows)

    today_str = datetime.now(UTC).strftime("%Y-%m-%d")
    today_count = _exec_read(
        "SELECT COUNT(*) FROM queries WHERE ts LIKE ?", (f"{today_str}%",),
    )[0][0]

    cutoff_7d = (datetime.now(UTC) - timedelta(days=days)).isoformat()
    week_count = _exec_read(
        "SELECT COUNT(*) FROM queries WHERE ts >= ?", (cutoff_7d,),
    )[0][0]

    latencies = sorted(r["latency_ms"] for r in all_rows)
    avg_latency = sum(latencies) / len(latencies) if latencies else 0.0
    p95_latency = latencies[int(len(latencies) * 0.95)] if latencies else 0.0

    scores = [r["top1_score"] for r in all_rows if r["top1_score"] is not None]
    avg_score = sum(scores) / len(scores) if scores else None
    below = sum(1 for s in scores if s < 0.3)
    pct_below = (below / len(scores) * 100) if scores else 0.0

    kb_count = sum(1 for r in all_rows if r["route"] == "kb_only")
    no_ret_count = sum(1 for r in all_rows if r["route"] == "no_retrieval")

    return {
        "total_queries": total, "queries_today": today_count,
        "queries_7d": week_count,
        "avg_latency_ms": round(avg_latency, 1),
        "p95_latency_ms": round(p95_latency, 1),
        "avg_top1_score": round(avg_score, 3) if avg_score is not None else None,
        "pct_below_threshold": round(pct_below, 1),
        "kb_only_count": kb_count, "no_retrieval_count": no_ret_count,
    }


def get_retrieval_quality(days: int = 7) -> dict:
    """Retrieval quality metrics for kb_only queries."""
    cutoff = (datetime.now(UTC) - timedelta(days=days)).isoformat()
    rows = _exec_read(
        "SELECT top1_score, evidence_count FROM queries WHERE route = 'kb_only' AND ts >= ?",
        (cutoff,),
    )
    total = len(rows)
    scores = [r["top1_score"] for r in rows if r["top1_score"] is not None]
    avg_score = sum(scores) / len(scores) if scores else None
    below = sum(1 for s in scores if s < 0.3)
    pct_below = (below / len(scores) * 100) if scores else 0.0
    avg_evidence = sum(r["evidence_count"] for r in rows) / total if total else 0.0
    return {
        "avg_top1_score": round(avg_score, 3) if avg_score is not None else None,
        "pct_below_threshold": round(pct_below, 1),
        "avg_evidence_count": round(avg_evidence, 1),
        "total_evaluated": total,
    }


def get_agent_behavior(days: int = 7) -> dict:
    """Agent routing and retry metrics."""
    cutoff = (datetime.now(UTC) - timedelta(days=days)).isoformat()
    rows = _exec_read(
        "SELECT route, retrieval_loops, queries_generated, is_sufficient FROM queries WHERE ts >= ?",
        (cutoff,),
    )
    total = len(rows)
    if total == 0:
        return {"total_queries": 0, "kb_only_rate": 0.0, "retry_loop_rate": 0.0,
                "avg_queries_generated": 0.0, "sufficient_rate": 0.0}
    kb = sum(1 for r in rows if r["route"] == "kb_only")
    retries = sum(1 for r in rows if r["retrieval_loops"] > 1)
    avg_qg = sum(r["queries_generated"] for r in rows) / total
    sufficient = sum(1 for r in rows if r["is_sufficient"])
    return {
        "total_queries": total, "kb_only_rate": round(kb / total, 3),
        "retry_loop_rate": round(retries / total, 3),
        "avg_queries_generated": round(avg_qg, 1),
        "sufficient_rate": round(sufficient / total, 3),
    }


def get_last_ingestion_ts() -> str | None:
    """Return the timestamp of the most recent ingestion, or None."""
    rows = _exec_read("SELECT ts FROM ingestions ORDER BY id DESC LIMIT 1")
    return rows[0]["ts"] if rows else None
