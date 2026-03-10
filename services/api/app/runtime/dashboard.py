"""Dashboard API endpoints — RAG operations metrics and logs."""

from fastapi import APIRouter, HTTPException, Query

from app.service.dashboard import (
    get_dashboard_agent_behavior,
    get_dashboard_ingestions,
    get_dashboard_queries,
    get_dashboard_retrieval_quality,
    get_dashboard_stats,
)
from app.types import (
    AgentBehavior,
    DashboardStats,
    IngestionLogEntry,
    QueryLogEntry,
    RetrievalQuality,
)

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/stats", response_model=DashboardStats)
async def dashboard_stats():
    """Quick-status panel: corpus size, query counts, latency, scores."""
    try:
        return get_dashboard_stats()
    except Exception as e:
        raise HTTPException(status_code=503, detail="Failed to load dashboard stats") from e


@router.get("/queries", response_model=list[QueryLogEntry])
async def dashboard_queries(limit: int = Query(default=20, ge=1, le=100)):
    """Recent queries with retrieval metrics."""
    try:
        return get_dashboard_queries(limit=limit)
    except Exception as e:
        raise HTTPException(status_code=503, detail="Failed to load query log") from e


@router.get("/ingestions", response_model=list[IngestionLogEntry])
async def dashboard_ingestions(limit: int = Query(default=20, ge=1, le=100)):
    """Recent document ingestions with pipeline results."""
    try:
        return get_dashboard_ingestions(limit=limit)
    except Exception as e:
        raise HTTPException(status_code=503, detail="Failed to load ingestion log") from e


@router.get("/retrieval-quality", response_model=RetrievalQuality)
async def retrieval_quality(days: int = Query(default=7, ge=1, le=90)):
    """Retrieval quality metrics over a time window."""
    try:
        return get_dashboard_retrieval_quality(days=days)
    except Exception as e:
        raise HTTPException(status_code=503, detail="Failed to load retrieval quality") from e


@router.get("/agent-behavior", response_model=AgentBehavior)
async def agent_behavior(days: int = Query(default=7, ge=1, le=90)):
    """Agent routing and retry behavior metrics."""
    try:
        return get_dashboard_agent_behavior(days=days)
    except Exception as e:
        raise HTTPException(status_code=503, detail="Failed to load agent behavior") from e
