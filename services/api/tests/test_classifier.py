"""Tests for document classification."""

from unittest.mock import patch

from app.service.classifier import classify_document
from app.types import DocumentClassification


@patch("app.service.classifier.chat_completion")
def test_classify_returns_valid_category(mock_chat):
    """LLM classification maps to valid enum value."""
    mock_chat.return_value = '{"classification": "procedure", "confidence": 0.9}'
    result = classify_document("Step 1: Install the software. Step 2: Configure.")
    assert result == DocumentClassification.procedure


@patch("app.service.classifier.chat_completion")
def test_classify_unknown_falls_back(mock_chat):
    """Unknown classification falls back to general."""
    mock_chat.return_value = '{"classification": "unknown_type", "confidence": 0.5}'
    result = classify_document("Some text")
    assert result == DocumentClassification.general


@patch("app.service.classifier.chat_completion")
def test_classify_error_falls_back(mock_chat):
    """LLM errors fall back to general."""
    mock_chat.side_effect = RuntimeError("API down")
    result = classify_document("Some text")
    assert result == DocumentClassification.general


@patch("app.service.classifier.chat_completion")
def test_classify_truncates_input(mock_chat):
    """Long text gets truncated to 2000 chars."""
    mock_chat.return_value = '{"classification": "general", "confidence": 0.8}'
    long_text = "x" * 5000
    classify_document(long_text)
    call_args = mock_chat.call_args
    user_msg = call_args[1]["user_message"] if "user_message" in call_args[1] else call_args[0][1]
    # The message should contain at most 2000 chars of the document
    assert len(user_msg) < 2100
