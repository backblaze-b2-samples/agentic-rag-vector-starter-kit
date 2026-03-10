"""Tests for the document processing pipeline."""

from unittest.mock import patch

from app.service.pipeline import PROCESSABLE_TYPES, _generate_chunk_id, process_document
from app.types import DocumentClassification, DocumentStatus


def test_generate_chunk_id_deterministic():
    """Same inputs produce same chunk ID."""
    id1 = _generate_chunk_id("doc/key", 0)
    id2 = _generate_chunk_id("doc/key", 0)
    assert id1 == id2
    assert len(id1) == 16


def test_generate_chunk_id_unique():
    """Different inputs produce different chunk IDs."""
    id1 = _generate_chunk_id("doc/key", 0)
    id2 = _generate_chunk_id("doc/key", 1)
    assert id1 != id2


def test_unprocessable_type_returns_completed():
    """Non-text files get a completed status with 0 chunks."""
    result = process_document(b"binary", "uploads/img.png", "img.png", "image/png")
    assert result.status == DocumentStatus.completed
    assert result.chunk_count == 0


@patch("app.service.pipeline.add_chunks")
@patch("app.service.pipeline.delete_doc_chunks")
@patch("app.service.pipeline.embed_chunks")
@patch("app.service.pipeline.summarize_document")
@patch("app.service.pipeline.summarize_chunk")
@patch("app.service.pipeline.classify_document")
def test_pipeline_processes_text_file(
    mock_classify,
    mock_summarize_chunk,
    mock_summarize_doc,
    mock_embed,
    mock_delete,
    mock_add,
):
    """Full pipeline processes a text file end-to-end."""
    mock_classify.return_value = DocumentClassification.reference
    mock_summarize_chunk.return_value = "A chunk summary"
    mock_summarize_doc.return_value = "A document summary"
    mock_embed.return_value = [[0.1] * 1536]  # one vector
    mock_add.return_value = 1

    text = "This is a test document with enough content to be processed."
    result = process_document(
        text.encode("utf-8"), "uploads/test.txt", "test.txt", "text/plain"
    )

    assert result.status == DocumentStatus.completed
    assert result.classification == DocumentClassification.reference
    assert result.summary == "A document summary"
    assert result.chunk_count >= 1
    mock_delete.assert_called_once_with("uploads/test.txt")
    mock_add.assert_called_once()


@patch("app.service.pipeline.chunk_document")
def test_pipeline_handles_errors_gracefully(mock_chunk):
    """Pipeline errors return failed status, not exceptions."""
    mock_chunk.side_effect = RuntimeError("Extraction failed")
    result = process_document(
        b"text", "uploads/bad.txt", "bad.txt", "text/plain"
    )
    assert result.status == DocumentStatus.failed
    assert "Extraction failed" in result.error_message


def test_processable_types_defined():
    """Ensure processable types are documented."""
    assert "application/pdf" in PROCESSABLE_TYPES
    assert "text/plain" in PROCESSABLE_TYPES
