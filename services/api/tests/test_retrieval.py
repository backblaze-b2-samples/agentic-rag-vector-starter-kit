"""Tests for the agentic retrieval engine."""

from unittest.mock import patch

from app.service.reranker import validate_evidence
from app.service.retrieval import (
    _step2_classify_intent,
    _step3_plan_queries,
    _step5_fuse_and_dedup,
    retrieve,
)
from app.types import CandidateChunk, RankedEvidence, RetrievalRoute


@patch("app.service.retrieval.chat_completion")
def test_classify_intent_kb_only(mock_chat):
    """Questions about documents route to kb_only."""
    mock_chat.return_value = '{"route": "kb_only", "intent_type": "q_and_a"}'
    result = _step2_classify_intent("What is the refund policy?")
    assert result.route == RetrievalRoute.kb_only
    assert result.intent_type == "q_and_a"


@patch("app.service.retrieval.chat_completion")
def test_classify_intent_no_retrieval(mock_chat):
    """Conversational messages route to no_retrieval."""
    mock_chat.return_value = '{"route": "no_retrieval", "intent_type": "general"}'
    result = _step2_classify_intent("Hello!")
    assert result.route == RetrievalRoute.no_retrieval


@patch("app.service.retrieval.chat_completion")
def test_classify_intent_error_defaults_kb(mock_chat):
    """LLM errors default to kb_only."""
    mock_chat.side_effect = RuntimeError("API down")
    result = _step2_classify_intent("What is X?")
    assert result.route == RetrievalRoute.kb_only


@patch("app.service.retrieval.chat_completion")
def test_plan_queries_generates_variants(mock_chat):
    """Query planning generates multiple variants."""
    mock_chat.return_value = (
        '{"variants": ['
        '{"query": "refund policy details", "query_type": "semantic"},'
        '{"query": "refund return policy", "query_type": "keyword"}'
        '], "reasoning": "Two approaches"}'
    )
    plan = _step3_plan_queries("What is the refund policy?")
    assert len(plan.variants) >= 2
    assert any(v.query_type == "semantic" for v in plan.variants)


@patch("app.service.retrieval.chat_completion")
def test_plan_queries_includes_original(mock_chat):
    """Query plan always includes the original question."""
    mock_chat.return_value = (
        '{"variants": [{"query": "other query", "query_type": "semantic"}],'
        ' "reasoning": "test"}'
    )
    plan = _step3_plan_queries("original question")
    queries = [v.query for v in plan.variants]
    assert "original question" in queries


def test_fuse_and_dedup_removes_duplicates():
    """Fusion deduplicates by chunk_id."""
    c1 = CandidateChunk(
        chunk_id="abc", doc_id="d1", doc_title="Doc", section_path="S1",
        text="text1", score=0.9, source="vector", source_filename="f.txt",
    )
    c2 = CandidateChunk(
        chunk_id="abc", doc_id="d1", doc_title="Doc", section_path="S1",
        text="text1", score=0.8, source="vector", source_filename="f.txt",
    )
    c3 = CandidateChunk(
        chunk_id="def", doc_id="d2", doc_title="Doc2", section_path="S2",
        text="text2", score=0.7, source="vector", source_filename="g.txt",
    )
    result = _step5_fuse_and_dedup([c1, c2, c3])
    chunk_ids = [c.chunk_id for c in result]
    assert len(chunk_ids) == 2
    assert "abc" in chunk_ids
    assert "def" in chunk_ids


def test_fuse_rrf_boosts_multi_query_hits():
    """Chunks appearing in multiple query results get higher RRF scores."""
    c1 = CandidateChunk(
        chunk_id="top", doc_id="d1", doc_title="Doc", section_path="S1",
        text="text", score=0.9, source="vector", source_filename="f.txt",
    )
    c2 = CandidateChunk(
        chunk_id="other", doc_id="d2", doc_title="Doc2", section_path="S2",
        text="text2", score=0.8, source="vector", source_filename="g.txt",
    )
    # "top" appears twice (from two query variants)
    c3 = CandidateChunk(
        chunk_id="top", doc_id="d1", doc_title="Doc", section_path="S1",
        text="text", score=0.7, source="vector", source_filename="f.txt",
    )
    result = _step5_fuse_and_dedup([c1, c2, c3])
    # "top" should be ranked first (higher RRF score from two appearances)
    assert result[0].chunk_id == "top"


@patch("app.service.reranker.chat_completion")
def test_validate_evidence_sufficient(mock_chat):
    """Evidence validation returns sufficient when LLM says so."""
    mock_chat.return_value = '{"is_sufficient": true, "gap_description": ""}'
    evidence = [
        RankedEvidence(
            chunk_id="a", doc_id="d", doc_title="T", section_path="S",
            text="answer text", relevance_score=0.9, source_filename="f.txt",
        )
    ]
    result = validate_evidence("question?", evidence)
    assert result.is_sufficient is True


def test_validate_evidence_empty():
    """Empty evidence is not sufficient."""
    result = validate_evidence("question?", [])
    assert result.is_sufficient is False
    assert "No relevant evidence" in result.gap_description


@patch("app.service.retrieval._step2_classify_intent")
def test_retrieve_no_retrieval_route(mock_intent):
    """No-retrieval route returns empty evidence fast."""
    from app.types import IntentClassification
    mock_intent.return_value = IntentClassification(
        route=RetrievalRoute.no_retrieval, intent_type="general",
    )
    evidence_set, metrics = retrieve("Hello there!")
    assert metrics.route == "no_retrieval"
    assert metrics.queries_generated == 0
    assert evidence_set.evidence == []
