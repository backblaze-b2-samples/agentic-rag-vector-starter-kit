"""Types for the agentic retrieval pipeline."""

from enum import StrEnum

from pydantic import BaseModel


class RetrievalRoute(StrEnum):
    """How the agent should handle this request."""
    kb_only = "kb_only"
    no_retrieval = "no_retrieval"


class IntentClassification(BaseModel):
    """Result of classifying user intent."""
    route: RetrievalRoute
    intent_type: str  # q_and_a, troubleshooting, action, etc.
    filters: dict = {}  # tenant_id, product_area, etc.


class QueryVariant(BaseModel):
    """A single query variant for retrieval."""
    query: str
    query_type: str  # "semantic", "keyword", "identifier"
    source: str = "vector"  # "vector" or "lexical"
    k: int = 20  # number of results to request


class QueryPlan(BaseModel):
    """The agent's plan for retrieving evidence."""
    variants: list[QueryVariant]
    reasoning: str  # why these queries were chosen


class CandidateChunk(BaseModel):
    """A retrieved chunk before reranking."""
    chunk_id: str
    doc_id: str
    doc_title: str
    section_path: str
    text: str
    score: float
    source: str  # "vector" or "lexical"
    source_filename: str
    page: int | None = None


class RankedEvidence(BaseModel):
    """A chunk after reranking with relevance score."""
    chunk_id: str
    doc_id: str
    doc_title: str
    section_path: str
    text: str
    relevance_score: float  # 0.0-1.0 from reranker
    source_filename: str
    page: int | None = None


class EvidenceSet(BaseModel):
    """Final set of evidence for answer generation."""
    evidence: list[RankedEvidence]
    is_sufficient: bool
    gap_description: str = ""  # what's missing if insufficient


class RetrievalMetrics(BaseModel):
    """Logged metrics for observability."""
    route: str
    queries_generated: int
    total_candidates: int
    post_fusion_candidates: int
    post_rerank_count: int
    evidence_count: int
    retrieval_loops: int
    latency_ms: float
