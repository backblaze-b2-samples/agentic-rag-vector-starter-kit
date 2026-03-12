"""Reranking — cross-encoder relevance scoring of candidate chunks.

Uses a lightweight cross-encoder model (22M params, CPU) instead of
per-candidate LLM calls. ~100-200ms for 20 candidates vs ~10s for 20 LLM calls.
"""

import json
import logging
import re

from app.repo import chat_completion
from app.repo.cross_encoder_client import score_pairs
from app.types import CandidateChunk, EvidenceSet, RankedEvidence

logger = logging.getLogger(__name__)

RERANK_TOP_K = 12
# Cross-encoder logit threshold; ms-marco-MiniLM-L-6-v2 scores range ~[-10, 10].
# -3.0 keeps borderline results; true garbage is typically < -5.
CROSS_ENCODER_THRESHOLD = -3.0


def _extract_json(text: str) -> dict:
    """Parse JSON from LLM output, stripping markdown code fences if present."""
    cleaned = text.strip()
    cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
    cleaned = re.sub(r"\s*```$", "", cleaned)
    return json.loads(cleaned.strip())


_SUFFICIENCY_PROMPT = """Given these evidence chunks and the user's question, assess:
1. Do the chunks directly answer the question?
2. Are there contradictions?
3. Is critical information missing?

Respond with JSON only:
{"is_sufficient": true|false, "gap_description": "<what's missing if insufficient>"}"""


def rerank_candidates(
    question: str, candidates: list[CandidateChunk],
) -> list[RankedEvidence]:
    """Cross-encoder reranking of top candidates.

    Scores each candidate against the question using a cross-encoder model,
    filters by threshold, and returns the top K by relevance score.
    """
    to_rerank = candidates[:20]
    if not to_rerank:
        return []

    # Score all candidates via cross-encoder; fall back to RRF scores on failure
    try:
        passages = [c.text[:1500] for c in to_rerank]
        scores = score_pairs(question, passages)
    except Exception:
        logger.warning("Cross-encoder failed, falling back to candidate scores", exc_info=True)
        scores = [c.score for c in to_rerank]

    ranked: list[RankedEvidence] = []
    for candidate, score in zip(to_rerank, scores, strict=True):
        if score >= CROSS_ENCODER_THRESHOLD:
            ranked.append(RankedEvidence(
                chunk_id=candidate.chunk_id,
                doc_id=candidate.doc_id,
                doc_title=candidate.doc_title,
                section_path=candidate.section_path,
                text=candidate.text,
                relevance_score=score,
                source_filename=candidate.source_filename,
                page=candidate.page,
            ))

    ranked.sort(key=lambda e: e.relevance_score, reverse=True)
    logger.info("[reranker] %d/%d candidates scored >= %.1f threshold",
                len(ranked), len(to_rerank), CROSS_ENCODER_THRESHOLD)
    return ranked[:RERANK_TOP_K]


def validate_evidence(
    question: str, evidence: list[RankedEvidence],
) -> EvidenceSet:
    """Check if evidence is sufficient to answer the question."""
    if not evidence:
        return EvidenceSet(
            evidence=[],
            is_sufficient=False,
            gap_description="No relevant evidence found",
        )

    evidence_text = "\n---\n".join(
        f"[{i+1}] {e.doc_title} > {e.section_path}\n{e.text[:500]}"
        for i, e in enumerate(evidence[:8])
    )

    try:
        response = chat_completion(
            system_prompt=_SUFFICIENCY_PROMPT,
            user_message=f"Question: {question}\n\nEvidence:\n{evidence_text}",
            temperature=0.0,
        )
        data = _extract_json(response)
        return EvidenceSet(
            evidence=evidence,
            is_sufficient=data.get("is_sufficient", True),
            gap_description=data.get("gap_description", ""),
        )
    except Exception:
        logger.warning("Evidence validation failed", exc_info=True)
        return EvidenceSet(evidence=evidence, is_sufficient=len(evidence) >= 2)
