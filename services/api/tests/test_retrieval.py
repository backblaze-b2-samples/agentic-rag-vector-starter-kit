"""Tests for the agentic retrieval engine."""

from unittest.mock import patch

from app.service.reranker import validate_evidence
from app.service.retrieval import (
    _classify_and_plan,
    _fuse_and_dedup,
    retrieve,
)
from app.types import CandidateChunk, RankedEvidence, RetrievalRoute


@patch("app.service.retrieval.chat_completion")
def test_classify_and_plan_kb_only(mock_chat):
    """Questions about documents route to kb_only with query variants."""
    mock_chat.return_value = (
        '{"route": "kb_only", "intent_type": "q_and_a",'
        ' "variants": [{"query": "refund policy", "query_type": "semantic"}],'
        ' "reasoning": "test"}'
    )
    intent, plan = _classify_and_plan("What is the refund policy?")
    assert intent.route == RetrievalRoute.kb_only
    assert intent.intent_type == "q_and_a"
    assert len(plan.variants) >= 1


@patch("app.service.retrieval.chat_completion")
def test_classify_and_plan_no_retrieval(mock_chat):
    """Conversational messages route to no_retrieval."""
    mock_chat.return_value = '{"route": "no_retrieval", "intent_type": "general", "variants": []}'
    intent, plan = _classify_and_plan("Hello!")
    assert intent.route == RetrievalRoute.no_retrieval
    assert len(plan.variants) == 0


@patch("app.service.retrieval.chat_completion")
def test_classify_and_plan_doc_info(mock_chat):
    """Questions about documents themselves route to doc_info."""
    mock_chat.return_value = '{"route": "doc_info", "intent_type": "general", "variants": []}'
    intent, _plan = _classify_and_plan("What documents do you have?")
    assert intent.route == RetrievalRoute.doc_info


@patch("app.service.retrieval.chat_completion")
def test_classify_and_plan_error_defaults_kb(mock_chat):
    """LLM errors default to kb_only with original question as variant."""
    mock_chat.side_effect = RuntimeError("API down")
    intent, plan = _classify_and_plan("What is X?")
    assert intent.route == RetrievalRoute.kb_only
    assert len(plan.variants) == 1
    assert plan.variants[0].query == "What is X?"


@patch("app.service.retrieval.chat_completion")
def test_classify_and_plan_includes_original(mock_chat):
    """Query plan always includes the original question."""
    mock_chat.return_value = (
        '{"route": "kb_only", "intent_type": "general",'
        ' "variants": [{"query": "other query", "query_type": "semantic"}],'
        ' "reasoning": "test"}'
    )
    _, plan = _classify_and_plan("original question")
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
    result = _fuse_and_dedup([c1, c2, c3])
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
    c3 = CandidateChunk(
        chunk_id="top", doc_id="d1", doc_title="Doc", section_path="S1",
        text="text", score=0.7, source="vector", source_filename="f.txt",
    )
    result = _fuse_and_dedup([c1, c2, c3])
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


@patch("app.service.retrieval._classify_and_plan")
def test_retrieve_no_retrieval_route(mock_classify):
    """No-retrieval route returns empty evidence fast."""
    from app.types import IntentClassification, QueryPlan
    mock_classify.return_value = (
        IntentClassification(route=RetrievalRoute.no_retrieval, intent_type="general"),
        QueryPlan(variants=[], reasoning="no retrieval"),
    )
    evidence_set, metrics = retrieve("Hello there!")
    assert metrics.route == "no_retrieval"
    assert metrics.queries_generated == 0
    assert evidence_set.evidence == []
