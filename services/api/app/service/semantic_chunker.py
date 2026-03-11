"""Semantic chunking — split text at topic boundaries using embedding similarity.

Embeds consecutive sentences and splits where cosine similarity drops below
a threshold, indicating a topic change. Falls back to character-based
splitting for short texts or when embeddings are unavailable.
"""

import logging
import re

import numpy as np

from app.repo import generate_embeddings

logger = logging.getLogger(__name__)

# Similarity threshold: split when consecutive sentence similarity drops below this
SIMILARITY_THRESHOLD = 0.75
# Minimum chunk size in characters (avoid tiny chunks)
MIN_CHUNK_SIZE = 200
# Maximum chunk size in characters (hard limit)
MAX_CHUNK_SIZE = 2000


def _split_sentences(text: str) -> list[str]:
    """Split text into sentences using regex patterns."""
    sentences = re.split(r'(?<=[.!?])\s+(?=[A-Z])', text)
    # Merge very short sentences with the next one
    merged: list[str] = []
    for s in sentences:
        s = s.strip()
        if not s:
            continue
        if merged and len(merged[-1]) < 50:
            merged[-1] = merged[-1] + " " + s
        else:
            merged.append(s)
    return merged


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    """Compute cosine similarity between two vectors."""
    va = np.array(a)
    vb = np.array(b)
    dot = np.dot(va, vb)
    norm = np.linalg.norm(va) * np.linalg.norm(vb)
    return float(dot / norm) if norm > 0 else 0.0


def semantic_chunk(text: str) -> list[str]:
    """Split text into chunks at semantic topic boundaries.

    1. Split into sentences
    2. Embed each sentence
    3. Find drop-offs in cosine similarity between consecutive sentences
    4. Split at those boundaries, respecting min/max size constraints
    """
    sentences = _split_sentences(text)
    if len(sentences) <= 2:
        return [text] if text.strip() else []

    # Embed all sentences in one batch
    try:
        vectors = generate_embeddings(sentences)
    except Exception:
        logger.warning("Semantic chunking embedding failed, returning full text")
        return [text] if text.strip() else []

    if len(vectors) != len(sentences):
        return [text] if text.strip() else []

    # Find split points where similarity drops below threshold
    split_indices: list[int] = []
    for i in range(len(vectors) - 1):
        sim = _cosine_similarity(vectors[i], vectors[i + 1])
        if sim < SIMILARITY_THRESHOLD:
            split_indices.append(i + 1)

    # Build chunks from split points
    chunks: list[str] = []
    prev = 0
    for idx in split_indices:
        chunk_text = " ".join(sentences[prev:idx]).strip()
        if chunk_text:
            chunks.append(chunk_text)
        prev = idx
    # Last chunk
    remainder = " ".join(sentences[prev:]).strip()
    if remainder:
        chunks.append(remainder)

    # Post-process: merge tiny chunks, split oversized chunks
    final: list[str] = []
    for chunk in chunks:
        if final and len(final[-1]) < MIN_CHUNK_SIZE:
            final[-1] = final[-1] + " " + chunk
        elif len(chunk) > MAX_CHUNK_SIZE:
            # Hard split oversized chunks
            for i in range(0, len(chunk), MAX_CHUNK_SIZE):
                piece = chunk[i:i + MAX_CHUNK_SIZE].strip()
                if piece:
                    final.append(piece)
        else:
            final.append(chunk)

    logger.info("Semantic chunking: %d sentences → %d chunks", len(sentences), len(final))
    return final
