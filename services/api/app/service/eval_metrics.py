"""RAGAS-inspired evaluation metrics for retrieval quality.

Computes faithfulness (is the answer grounded in evidence?) and
context precision (are the retrieved chunks relevant?) using LLM-as-judge.
Scores are logged per-query for dashboard analytics.
"""

import json
import logging
import re

from app.repo import chat_completion

logger = logging.getLogger(__name__)

_FAITHFULNESS_PROMPT = """You are an answer quality evaluator. Given an answer and
the evidence chunks it was based on, score how faithful the answer is to the evidence.

Score from 0.0 to 1.0:
- 1.0: Every claim in the answer is directly supported by the evidence
- 0.5: Some claims are supported, others are extrapolated
- 0.0: The answer contradicts or ignores the evidence

Respond with JSON only: {"score": <float>, "reasoning": "<brief>"}"""

_CONTEXT_PRECISION_PROMPT = """You are a retrieval quality evaluator. Given a question
and retrieved context chunks, score how relevant the chunks are to the question.

Score from 0.0 to 1.0:
- 1.0: All chunks are highly relevant and useful for answering
- 0.5: Some chunks are relevant, others are noise
- 0.0: None of the chunks are relevant

Respond with JSON only: {"score": <float>, "reasoning": "<brief>"}"""


def _extract_json(text: str) -> dict:
    """Parse JSON from LLM output, stripping markdown code fences."""
    cleaned = text.strip()
    cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
    cleaned = re.sub(r"\s*```$", "", cleaned)
    return json.loads(cleaned.strip())


def score_faithfulness(answer: str, evidence_texts: list[str]) -> float | None:
    """Score how well the answer is grounded in the provided evidence.

    Returns 0.0-1.0 score, or None on failure.
    """
    if not answer or not evidence_texts:
        return None
    evidence_str = "\n---\n".join(
        f"[{i+1}] {t[:500]}" for i, t in enumerate(evidence_texts[:8])
    )
    try:
        response = chat_completion(
            system_prompt=_FAITHFULNESS_PROMPT,
            user_message=f"Answer:\n{answer[:2000]}\n\nEvidence:\n{evidence_str}",
            temperature=0.0,
        )
        data = _extract_json(response)
        return max(0.0, min(1.0, float(data.get("score", 0.0))))
    except Exception:
        logger.warning("Faithfulness scoring failed", exc_info=True)
        return None


def score_context_precision(question: str, context_texts: list[str]) -> float | None:
    """Score how relevant the retrieved context is to the question.

    Returns 0.0-1.0 score, or None on failure.
    """
    if not question or not context_texts:
        return None
    context_str = "\n---\n".join(
        f"[{i+1}] {t[:500]}" for i, t in enumerate(context_texts[:8])
    )
    try:
        response = chat_completion(
            system_prompt=_CONTEXT_PRECISION_PROMPT,
            user_message=f"Question: {question}\n\nContext:\n{context_str}",
            temperature=0.0,
        )
        data = _extract_json(response)
        return max(0.0, min(1.0, float(data.get("score", 0.0))))
    except Exception:
        logger.warning("Context precision scoring failed", exc_info=True)
        return None
