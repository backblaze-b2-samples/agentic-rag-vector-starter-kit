"""Integration tests for dashboard API endpoints."""

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


def _seed_data():
    """Insert sample query and ingestion records."""
    query_log.log_query(
        query="How do I reset?", route="kb_only", queries_generated=3,
        total_candidates=25, post_fusion_candidates=15, post_rerank_count=5,
        evidence_count=5, retrieval_loops=1, latency_ms=120.5,
        top1_score=0.82, top5_scores=[0.82, 0.7], is_sufficient=True,
    )
    query_log.log_ingestion(
        doc_id="doc1", filename="guide.pdf", status="completed",
        chunk_count=8, total_tokens=3200, classification="technical",
        error_message=None,
    )


@pytest.mark.asyncio
async def test_dashboard_stats(client):
    _seed_data()
    with patch("app.service.dashboard.get_table_stats", return_value={"total_chunks": 100}), \
         patch("app.service.dashboard.list_files", return_value=[{"key": "a"}]):
        resp = await client.get("/dashboard/stats")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_queries"] == 1
    assert data["total_documents"] == 1
    assert data["total_chunks"] == 100


@pytest.mark.asyncio
async def test_dashboard_queries(client):
    _seed_data()
    resp = await client.get("/dashboard/queries?limit=5")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["query"] == "How do I reset?"


@pytest.mark.asyncio
async def test_dashboard_ingestions(client):
    _seed_data()
    resp = await client.get("/dashboard/ingestions?limit=5")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["filename"] == "guide.pdf"


@pytest.mark.asyncio
async def test_dashboard_retrieval_quality(client):
    _seed_data()
    resp = await client.get("/dashboard/retrieval-quality")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_evaluated"] == 1
    assert data["avg_top1_score"] == 0.82


@pytest.mark.asyncio
async def test_dashboard_agent_behavior(client):
    _seed_data()
    resp = await client.get("/dashboard/agent-behavior")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_queries"] == 1
    assert data["sufficient_rate"] == 1.0
