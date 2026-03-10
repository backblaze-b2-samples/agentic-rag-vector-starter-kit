"""Unit tests for the SQLite query and ingestion log."""

from unittest.mock import patch

import pytest

from app.repo import query_log


@pytest.fixture(autouse=True)
def _use_temp_db(tmp_path):
    """Point query_log at a temp SQLite file for test isolation."""
    db_path = tmp_path / "test_log.sqlite"
    with patch.object(query_log, "_DB_PATH", db_path):
        query_log._initialized = False
        yield
    query_log._initialized = False


def _insert_query(**overrides):
    defaults = dict(
        query="test question", route="kb_only", queries_generated=3,
        total_candidates=30, post_fusion_candidates=20, post_rerank_count=5,
        evidence_count=5, retrieval_loops=1, latency_ms=150.0,
        top1_score=0.85, top5_scores=[0.85, 0.7, 0.6, 0.5, 0.4],
        is_sufficient=True,
    )
    defaults.update(overrides)
    query_log.log_query(**defaults)


def test_log_and_get_queries():
    _insert_query(query="first")
    _insert_query(query="second")
    rows = query_log.get_recent_queries(limit=10)
    assert len(rows) == 2
    assert rows[0]["query"] == "second"  # most recent first
    assert rows[0]["is_sufficient"] is True


def test_log_and_get_ingestions():
    query_log.log_ingestion(
        doc_id="doc1", filename="report.pdf", status="completed",
        chunk_count=10, total_tokens=5000, classification="technical",
        error_message=None,
    )
    rows = query_log.get_recent_ingestions(limit=10)
    assert len(rows) == 1
    assert rows[0]["filename"] == "report.pdf"
    assert rows[0]["error_message"] is None


def test_get_query_stats_empty():
    stats = query_log.get_query_stats()
    assert stats["total_queries"] == 0
    assert stats["avg_latency_ms"] == 0.0


def test_get_query_stats_with_data():
    _insert_query(latency_ms=100.0, route="kb_only", top1_score=0.9)
    _insert_query(latency_ms=200.0, route="no_retrieval", top1_score=None)
    stats = query_log.get_query_stats()
    assert stats["total_queries"] == 2
    assert stats["kb_only_count"] == 1
    assert stats["no_retrieval_count"] == 1
    assert stats["avg_latency_ms"] == 150.0


def test_get_retrieval_quality_empty():
    result = query_log.get_retrieval_quality()
    assert result["total_evaluated"] == 0
    assert result["avg_top1_score"] is None


def test_get_retrieval_quality_with_data():
    _insert_query(route="kb_only", top1_score=0.8, evidence_count=4)
    _insert_query(route="kb_only", top1_score=0.2, evidence_count=2)
    result = query_log.get_retrieval_quality()
    assert result["total_evaluated"] == 2
    assert result["avg_top1_score"] == 0.5
    assert result["pct_below_threshold"] == 50.0


def test_get_agent_behavior_empty():
    result = query_log.get_agent_behavior()
    assert result["total_queries"] == 0


def test_get_agent_behavior_with_data():
    _insert_query(route="kb_only", retrieval_loops=1, is_sufficient=True)
    _insert_query(route="kb_only", retrieval_loops=2, is_sufficient=False)
    result = query_log.get_agent_behavior()
    assert result["total_queries"] == 2
    assert result["retry_loop_rate"] == 0.5
    assert result["sufficient_rate"] == 0.5


def test_get_last_ingestion_ts_empty():
    assert query_log.get_last_ingestion_ts() is None


def test_get_last_ingestion_ts_with_data():
    query_log.log_ingestion(
        doc_id="d1", filename="a.pdf", status="completed",
        chunk_count=5, total_tokens=1000, classification="general",
        error_message=None,
    )
    ts = query_log.get_last_ingestion_ts()
    assert ts is not None
    assert "T" in ts  # ISO format
