"""Tests for document chunking logic."""

from unittest.mock import patch

from app.service.chunker import _detect_section_path, _split_text, chunk_document


def test_split_text_short():
    """Text shorter than chunk_size returns single chunk."""
    result = _split_text("Hello world", chunk_size=100, chunk_overlap=20)
    assert result == ["Hello world"]


def test_split_text_empty():
    """Empty text returns empty list."""
    result = _split_text("", chunk_size=100, chunk_overlap=20)
    assert result == []


def test_split_text_paragraphs():
    """Text with paragraph breaks splits on them."""
    text = "First paragraph.\n\nSecond paragraph.\n\nThird paragraph."
    result = _split_text(text, chunk_size=30, chunk_overlap=5)
    assert len(result) >= 2
    assert "First paragraph." in result[0]


def test_split_text_respects_max_size():
    """No chunk exceeds chunk_size (within tolerance for overlap edge cases)."""
    text = "word " * 500  # ~2500 chars
    result = _split_text(text, chunk_size=200, chunk_overlap=20)
    assert all(len(c) <= 250 for c in result)  # some tolerance for splits


def test_detect_section_path_markdown():
    """Detects markdown headings."""
    text = "## Getting Started\nSome content here"
    assert _detect_section_path(text, 0) == "Getting Started"


def test_detect_section_path_fallback():
    """Falls back to 'Chunk N' when no heading found."""
    text = "some random text without any heading pattern that is lowercase"
    result = _detect_section_path(text, 4)
    assert result == "Chunk 5"


def test_chunk_document_plain_text():
    """Plain text files get chunked."""
    text = "Section one content.\n\nSection two content.\n\nSection three content."
    file_data = text.encode("utf-8")
    chunks = chunk_document(file_data, "text/plain", "test.txt")
    assert len(chunks) >= 1
    assert all("text" in c for c in chunks)
    assert all("chunk_index" in c for c in chunks)
    assert all("total_chunks" in c for c in chunks)


def test_chunk_document_unsupported_type():
    """Unsupported content types return empty list."""
    result = chunk_document(b"data", "image/png", "photo.png")
    assert result == []


@patch("app.service.chunker.settings")
def test_chunk_document_respects_max_chunks(mock_settings):
    """Chunks get truncated at max_chunks_per_doc."""
    mock_settings.max_chunks_per_doc = 3
    mock_settings.chunk_size = 20
    mock_settings.chunk_overlap = 5
    text = "\n\n".join(f"Paragraph {i} with some content." for i in range(20))
    chunks = chunk_document(text.encode("utf-8"), "text/plain", "big.txt")
    assert len(chunks) <= 3
