"""Reranking — LLM-based relevance scoring of candidate chunks."""

import json
import logging

from app.repo import chat_completion
from app.types import CandidateChunk, EvidenceSet, RankedEvidence

logger = logging.getLogger(__name__)

RERANK_TOP_K = 12
CONFIDENCE_THRESHOLD = 0.3

_RERANK_PROMPT = """Rate how relevant this text chunk is to the user's question.
Score from 0.0 (irrelevant) to 1.0 (directly answers the question).

Respond with JSON only: {"score": <float>, "reason": "<brief>"}"""

_SUFFICIENCY_PROMPT = """Given these evidence chunks and the user's question, assess:
1. Do the chunks directly answer the question?
2. Are there contradictions?
3. Is critical information missing?

Respond with JSON only:
{"is_sufficient": true|false, "gap_description": "<what's missing if insufficient>"}"""


def rerank_candidates(
    question: str, candidates: list[CandidateChunk],
) -> list[RankedEvidence]:
    """LLM-based reranking of top candidates.

    Scores each candidate against the question, filters by confidence threshold,
    and returns the top K by relevance score.
    """
    to_rerank = candidates[:20]
    ranked: list[RankedEvidence] = []

    for candidate in to_rerank:
        try:
            response = chat_completion(
                system_prompt=_RERANK_PROMPT,
                user_message=f"Question: {question}\n\nChunk:\n{candidate.text[:1500]}",
                temperature=0.0,
            )
            data = json.loads(response.strip())
            score = float(data.get("score", 0.0))
        except Exception:
            score = candidate.score  # fallback to vector score

        if score >= CONFIDENCE_THRESHOLD:
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
        data = json.loads(response.strip())
        return EvidenceSet(
            evidence=evidence,
            is_sufficient=data.get("is_sufficient", True),
            gap_description=data.get("gap_description", ""),
        )
    except Exception:
        logger.warning("Evidence validation failed", exc_info=True)
        return EvidenceSet(evidence=evidence, is_sufficient=len(evidence) >= 2)
