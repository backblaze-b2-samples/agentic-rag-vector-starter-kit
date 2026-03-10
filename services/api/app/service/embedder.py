"""Embedding generation — batch embed document chunks via LangChain."""

import logging

from app.repo import generate_embeddings

logger = logging.getLogger(__name__)

# Max texts per embedding API call to stay within rate limits
_BATCH_SIZE = 100


def embed_chunks(texts: list[str]) -> list[list[float]]:
    """Generate embeddings for a list of chunk texts.

    Processes in batches to respect API limits.
    Returns list of float vectors aligned with input texts.
    """
    if not texts:
        return []

    all_vectors: list[list[float]] = []

    for i in range(0, len(texts), _BATCH_SIZE):
        batch = texts[i : i + _BATCH_SIZE]
        try:
            vectors = generate_embeddings(batch)
        except Exception:
            logger.exception("Embedding failed for batch %d-%d", i, min(i + _BATCH_SIZE, len(texts)))
            raise
        all_vectors.extend(vectors)
        logger.info(
            "Embedded batch %d-%d of %d",
            i,
            min(i + _BATCH_SIZE, len(texts)),
            len(texts),
        )

    return all_vectors
