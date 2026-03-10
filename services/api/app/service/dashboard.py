"""Dashboard service — aggregates query log data with corpus stats."""

import logging

from app.repo import (
    get_agent_behavior,
    get_last_ingestion_ts,
    get_query_stats,
    get_recent_ingestions,
    get_recent_queries,
    get_retrieval_quality,
    get_table_stats,
)
from app.repo.b2_client import list_files
from app.types import (
    AgentBehavior,
    DashboardStats,
    IngestionLogEntry,
    QueryLogEntry,
    RetrievalQuality,
)

logger = logging.getLogger(__name__)


def get_dashboard_stats() -> DashboardStats:
    """Build the quick-status panel data."""
    query_stats = get_query_stats()

    # Corpus stats from LanceDB
    try:
        table_stats = get_table_stats()
        total_chunks = table_stats["total_chunks"]
    except Exception:
        logger.warning("Failed to get LanceDB stats", exc_info=True)
        total_chunks = 0

    # Document count from B2
    try:
        files = list_files()
        total_documents = len(files)
    except Exception:
        logger.warning("Failed to get B2 file count", exc_info=True)
        total_documents = 0

    return DashboardStats(
        total_queries=query_stats["total_queries"],
        queries_today=query_stats["queries_today"],
        queries_7d=query_stats["queries_7d"],
        avg_latency_ms=query_stats["avg_latency_ms"],
        p95_latency_ms=query_stats["p95_latency_ms"],
        avg_top1_score=query_stats["avg_top1_score"],
        pct_below_threshold=query_stats["pct_below_threshold"],
        kb_only_count=query_stats["kb_only_count"],
        no_retrieval_count=query_stats["no_retrieval_count"],
        total_documents=total_documents,
        total_chunks=total_chunks,
        last_ingestion_ts=get_last_ingestion_ts(),
    )


def get_dashboard_queries(limit: int = 20) -> list[QueryLogEntry]:
    """Return recent query log entries as typed models."""
    rows = get_recent_queries(limit=limit)
    return [QueryLogEntry(**r) for r in rows]


def get_dashboard_ingestions(limit: int = 20) -> list[IngestionLogEntry]:
    """Return recent ingestion log entries as typed models."""
    rows = get_recent_ingestions(limit=limit)
    return [IngestionLogEntry(**r) for r in rows]


def get_dashboard_retrieval_quality(days: int = 7) -> RetrievalQuality:
    """Return retrieval quality metrics."""
    data = get_retrieval_quality(days=days)
    return RetrievalQuality(**data)


def get_dashboard_agent_behavior(days: int = 7) -> AgentBehavior:
    """Return agent routing and retry metrics."""
    data = get_agent_behavior(days=days)
    return AgentBehavior(**data)
