"""Contextual chunking — prepend LLM-generated context to each chunk.

Implements Anthropic's contextual retrieval technique: for each chunk,
generate a short context summary that situates it within the full document,
then prepend that context before embedding. This reduces retrieval failures
caused by chunks that lack surrounding context.
"""

import logging

from app.repo import chat_completion

logger = logging.getLogger(__name__)

_CONTEXT_PROMPT = """You are an expert at grounding document chunks for search retrieval.
Given a document chunk and a brief summary of the whole document, write 1-2 sentences
that situate this chunk within the document. Include key entities, topics, and section
context that would help a search system find this chunk.

Respond with ONLY the context sentences, nothing else."""


def generate_chunk_context(
    chunk_text: str, doc_summary: str, doc_title: str,
) -> str:
    """Generate a short context prefix for a chunk.

    Returns a 1-2 sentence context that situates the chunk within its document.
    Falls back to a simple title prefix on LLM failure.
    """
    try:
        response = chat_completion(
            system_prompt=_CONTEXT_PROMPT,
            user_message=(
                f"Document: {doc_title}\n"
                f"Document summary: {doc_summary}\n\n"
                f"Chunk:\n{chunk_text[:1500]}"
            ),
            temperature=0.0,
        )
        context = response.strip()
        if context and len(context) < 500:
            return context
        return f"From {doc_title}."
    except Exception:
        logger.warning("Context generation failed for chunk", exc_info=True)
        return f"From {doc_title}."


def contextualize_chunks(
    chunks: list[dict], doc_summary: str, doc_title: str,
) -> list[dict]:
    """Add contextual prefix to each chunk's text for better embedding.

    Modifies chunks in-place by prepending context to the text field
    and storing the original text in 'original_text'.
    """
    for chunk in chunks:
        context = generate_chunk_context(chunk["text"], doc_summary, doc_title)
        chunk["context_prefix"] = context
        # Prepend context to text for embedding (original preserved in chunk dict)
        chunk["text_with_context"] = f"{context}\n\n{chunk['text']}"
    logger.info("Contextualized %d chunks for '%s'", len(chunks), doc_title)
    return chunks
