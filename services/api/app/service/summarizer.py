"""Document summarization — generate chunk and document summaries."""

import logging

from app.repo import chat_completion

logger = logging.getLogger(__name__)

_CHUNK_SUMMARY_PROMPT = """Summarize this text chunk in 1-2 sentences. Be specific and factual.
Focus on the key information that would help someone decide if this chunk answers their question."""

_DOC_SUMMARY_PROMPT = """Given these chunk summaries from a single document, write a 2-3 sentence
summary of the entire document. Focus on what the document covers and who it's for."""


def summarize_chunk(text: str) -> str:
    """Generate a brief summary for a single chunk.

    Falls back to first 200 chars on error.
    """
    if len(text) < 100:
        return text

    try:
        return chat_completion(
            system_prompt=_CHUNK_SUMMARY_PROMPT,
            user_message=text,
            temperature=0.0,
        )
    except Exception:
        logger.warning("Chunk summarization failed", exc_info=True)
        return text[:200]


def summarize_document(chunk_summaries: list[str]) -> str:
    """Generate a whole-document summary from chunk summaries.

    Falls back to concatenation of first few summaries on error.
    """
    if not chunk_summaries:
        return ""

    # Combine chunk summaries, limiting input size
    combined = "\n".join(f"- {s}" for s in chunk_summaries[:20])

    try:
        return chat_completion(
            system_prompt=_DOC_SUMMARY_PROMPT,
            user_message=combined,
            temperature=0.0,
        )
    except Exception:
        logger.warning("Document summarization failed", exc_info=True)
        return "; ".join(chunk_summaries[:3])
