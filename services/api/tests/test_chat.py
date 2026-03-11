"""Tests for chat service with session persistence."""

from unittest.mock import patch

import pytest

from app.repo.session_store import _get_conn, _init_db
from app.service.chat import handle_chat
from app.types import ChatRequest, EvidenceSet, MessageRole, RetrievalMetrics


@pytest.fixture(autouse=True)
def _clean_sessions():
    """Reset session tables between tests."""
    _init_db()
    conn = _get_conn()
    try:
        conn.execute("DELETE FROM chat_messages")
        conn.execute("DELETE FROM chat_sessions")
        conn.commit()
    finally:
        conn.close()


@patch("app.service.chat.generate_title", return_value="Test Title")
@patch("app.service.chat.retrieve")
@patch("app.service.chat.chat_completion")
def test_handle_chat_no_retrieval(mock_chat, mock_retrieve, _mock_title):
    """Conversational messages skip retrieval and return direct response."""
    mock_retrieve.return_value = (
        EvidenceSet(evidence=[], is_sufficient=True),
        RetrievalMetrics(
            route="no_retrieval", queries_generated=0, total_candidates=0,
            post_fusion_candidates=0, post_rerank_count=0,
            evidence_count=0, retrieval_loops=0, latency_ms=50.0,
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


@patch("app.service.chat.generate_title", return_value="Test Title")
@patch("app.service.chat.get_presigned_url")
@patch("app.service.chat.retrieve")
@patch("app.service.chat.chat_completion")
def test_handle_chat_with_retrieval(mock_chat, mock_retrieve, mock_url, _mock_title):
    """KB queries return answer with citations."""
    from app.types import RankedEvidence

    evidence = [
        RankedEvidence(
            chunk_id="c1", doc_id="uploads/doc.pdf", doc_title="Guide",
            section_path="Setup", text="Install by running pip install ...",
            relevance_score=0.95, source_filename="doc.pdf", page=3,
        ),
    ]
    mock_retrieve.return_value = (
        EvidenceSet(evidence=evidence, is_sufficient=True),
        RetrievalMetrics(
            route="kb_only", queries_generated=3, total_candidates=30,
            post_fusion_candidates=15, post_rerank_count=1,
            evidence_count=1, retrieval_loops=1, latency_ms=500.0,
        ),
    )
    mock_chat.return_value = "To install, run pip install ... [1]"
    mock_url.return_value = "https://example.com/presigned"

    request = ChatRequest(message="How do I install it?")
    response = handle_chat(request)

    assert response.message.citations
    assert response.message.citations[0].index == 1
    assert response.message.citations[0].doc_title == "Guide"
    assert response.retrieval_metadata.route == "kb_only"


@patch("app.service.chat.generate_title", return_value="Test Title")
@patch("app.service.chat.retrieve")
@patch("app.service.chat.chat_completion")
def test_session_messages_persist(mock_chat, mock_retrieve, _mock_title):
    """Messages are stored in the session."""
    mock_retrieve.return_value = (
        EvidenceSet(evidence=[], is_sufficient=True),
        RetrievalMetrics(
            route="no_retrieval", queries_generated=0, total_candidates=0,
            post_fusion_candidates=0, post_rerank_count=0,
            evidence_count=0, retrieval_loops=0, latency_ms=10.0,
        ),
    )
    mock_chat.return_value = "Response"

    response = handle_chat(ChatRequest(message="First message"))
    sid = response.conversation_id

    # Follow-up in same session
    handle_chat(ChatRequest(message="Second message", session_id=sid))

    from app.repo.session_store import get_messages
    messages = get_messages(sid)
    assert len(messages) == 4  # user, assistant, user, assistant
    assert messages[0]["role"] == "user"
    assert messages[1]["role"] == "assistant"


def test_session_not_found():
    """Nonexistent session returns None."""
    from app.service.sessions import get_session_detail
    assert get_session_detail("nonexistent-id") is None
