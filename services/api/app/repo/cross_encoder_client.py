"""Cross-encoder repo layer — sentence-transformers reranking model.

Loads a lightweight cross-encoder (22M params, CPU-friendly) and scores
query-passage pairs for relevance. Model is cached after first load.
"""

import functools
import logging

logger = logging.getLogger(__name__)

# Small, fast, accurate for retrieval reranking (~100-200ms for 20 pairs on CPU)
MODEL_NAME = "cross-encoder/ms-marco-MiniLM-L-6-v2"


@functools.lru_cache(maxsize=1)
def _get_model():
    """Load cross-encoder model (cached after first call)."""
    from sentence_transformers import CrossEncoder

    logger.info("Loading cross-encoder model: %s", MODEL_NAME)
    model = CrossEncoder(MODEL_NAME)
    logger.info("Cross-encoder model loaded")
    return model


def score_pairs(query: str, passages: list[str]) -> list[float]:
    """Score query-passage pairs using cross-encoder.

    Returns list of relevance scores (higher = more relevant).
    Scores are on a logit scale; typical range [-10, 10].
    """
    if not passages:
        return []
    model = _get_model()
    pairs = [[query, p] for p in passages]
    scores = model.predict(pairs)
    return [float(s) for s in scores]
