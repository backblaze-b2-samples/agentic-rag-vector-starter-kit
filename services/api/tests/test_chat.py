"""Tests for chat service."""

from unittest.mock import patch

import pytest

from app.service.chat import clear_conversations, get_conversation, handle_chat
from app.types import ChatRequest, EvidenceSet, MessageRole, RetrievalMetrics


@pytest.fixture(autouse=True)
def _clean_conversations():
    """Reset conversation store between tests."""
    clear_conversations()
    yield
    clear_conversations()


@patch("app.service.chat.retrieve")
@patch("app.service.chat.chat_completion")
def test_handle_chat_no_retrieval(mock_chat, mock_retrieve):
    """Conversational messages skip retrieval and return direct response."""
    mock_retrieve.return_value = (
        EvidenceSet(evidence=[], is_sufficient=True),
        RetrievalMetrics(
            route="no_retrieval",
            queries_generated=0,
            total_candidates=0,
            post_fusion_candidates=0,
            post_rerank_count=0,
            evidence_count=0,
            retrieval_loops=0,
            latency_ms=50.0,
        ),
    )
    mock_chat.return_value = "Hello! How can I help you?"

    request = ChatRequest(message="Hi there!", conversation_id=None)
    response = handle_chat(request)

    assert response.conversation_id
    assert response.message.role == MessageRole.assistant
    assert response.message.content == "Hello! How can I help you?"
    assert response.message.citations == []
    assert response.retrieval_metadata.route == "no_retrieval"


@patch("app.service.chat.get_presigned_url")
@patch("app.service.chat.retrieve")
@patch("app.service.chat.chat_completion")
def test_handle_chat_with_retrieval(mock_chat, mock_retrieve, mock_url):
    """KB queries return answer with citations."""
    from app.types import RankedEvidence

    evidence = [
        RankedEvidence(
            chunk_id="c1",
            doc_id="uploads/doc.pdf",
            doc_title="Guide",
            section_path="Setup",
            text="Install by running pip install ...",
            relevance_score=0.95,
            source_filename="doc.pdf",
            page=3,
        ),
    ]
    mock_retrieve.return_value = (
        EvidenceSet(evidence=evidence, is_sufficient=True),
        RetrievalMetrics(
            route="kb_only",
            queries_generated=3,
            total_candidates=30,
            post_fusion_candidates=15,
            post_rerank_count=1,
            evidence_count=1,
            retrieval_loops=1,
            latency_ms=500.0,
        ),
    )
    mock_chat.return_value = "To install, run pip install ... [1]"
    mock_url.return_value = "https://example.com/presigned"

    request = ChatRequest(message="How do I install it?")
    response = handle_chat(request)

    assert response.message.citations
    assert response.message.citations[0].index == 1
    assert response.message.citations[0].doc_title == "Guide"
    assert response.message.citations[0].download_url == "https://example.com/presigned"
    assert response.retrieval_metadata.route == "kb_only"
    assert response.retrieval_metadata.evidence_used == 1


@patch("app.service.chat.retrieve")
@patch("app.service.chat.chat_completion")
def test_conversation_history_persists(mock_chat, mock_retrieve):
    """Messages are stored in conversation history."""
    mock_retrieve.return_value = (
        EvidenceSet(evidence=[], is_sufficient=True),
        RetrievalMetrics(
            route="no_retrieval",
            queries_generated=0,
            total_candidates=0,
            post_fusion_candidates=0,
            post_rerank_count=0,
            evidence_count=0,
            retrieval_loops=0,
            latency_ms=10.0,
        ),
    )
    mock_chat.return_value = "Response"

    request = ChatRequest(message="First message")
    response = handle_chat(request)
    conv_id = response.conversation_id

    # Send follow-up in same conversation
    request2 = ChatRequest(message="Second message", conversation_id=conv_id)
    handle_chat(request2)

    history = get_conversation(conv_id)
    assert len(history) == 4  # user, assistant, user, assistant
    assert history[0].role == MessageRole.user
    assert history[1].role == MessageRole.assistant


def test_get_conversation_nonexistent():
    """Nonexistent conversation returns empty list."""
    result = get_conversation("nonexistent-id")
    assert result == []
