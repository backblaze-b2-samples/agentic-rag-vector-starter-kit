"""Types for the RAG dashboard."""

from pydantic import BaseModel


class QueryLogEntry(BaseModel):
    """A single logged query with retrieval metrics."""
    id: int
    ts: str
    query: str
    route: str
    queries_generated: int
    total_candidates: int
    evidence_count: int
    retrieval_loops: int
    latency_ms: float
    top1_score: float | None
    is_sufficient: bool


class IngestionLogEntry(BaseModel):
    """A single logged document ingestion."""
    id: int
    ts: str
    doc_id: str
    filename: str
    status: str
    chunk_count: int
    total_tokens: int
    classification: str
    error_message: str | None
    summary: str = ""


class DashboardStats(BaseModel):
    """Aggregate stats for the dashboard quick-status panel."""
    total_queries: int
    queries_today: int
    queries_7d: int
    avg_latency_ms: float
    p95_latency_ms: float
    avg_top1_score: float | None
    pct_below_threshold: float
    kb_only_count: int
    no_retrieval_count: int
    total_documents: int
    total_chunks: int
    last_ingestion_ts: str | None


class RetrievalQuality(BaseModel):
    """Retrieval quality metrics over a time window."""
    avg_top1_score: float | None
    pct_below_threshold: float
    avg_evidence_count: float
    total_evaluated: int


class SessionSummary(BaseModel):
    """Session with aggregated RAGAS scores for dashboard."""
    session_id: str
    title: str
    created_at: str
    updated_at: str
    message_count: int
    avg_faithfulness: float | None
    avg_context_precision: float | None
    avg_latency_ms: float | None
    total_queries: int


class SessionMessageDetail(BaseModel):
    """Message with per-message evaluation scores."""
    id: int
    role: str
    content: str
    timestamp: str | None
    citations: list = []
    retrieval_metadata: dict | None = None
    faithfulness: float | None = None
    context_precision: float | None = None
    route: str | None = None
    latency_ms: float | None = None
    evidence_count: int | None = None


class AgentBehavior(BaseModel):
    """Agent routing and retry behavior metrics."""
    total_queries: int
    kb_only_rate: float
    retry_loop_rate: float
    avg_queries_generated: float
    sufficient_rate: float
