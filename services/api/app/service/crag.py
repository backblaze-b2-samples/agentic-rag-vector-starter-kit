"""Corrective RAG (CRAG) — grade retrieval quality and take corrective action.

After reranking, CRAG classifies the evidence as Correct/Ambiguous/Wrong:
- Correct: evidence directly answers the question → use as-is
- Ambiguous: partial evidence → keep evidence but add correction note
- Wrong: evidence is irrelevant → strip evidence, add note for LLM to
  rely on its own knowledge or decline to answer

Based on: https://arxiv.org/abs/2401.15884
"""

import json
import logging
import re

from app.repo import chat_completion
from app.types.crag import CRAGResult, RetrievalGrade
from app.types.retrieval import RankedEvidence

logger = logging.getLogger(__name__)

_GRADE_PROMPT = """You are a retrieval quality assessor. Given the user's question and
retrieved evidence chunks, classify the retrieval quality.

Respond with JSON only:
{
  "grade": "correct"|"ambiguous"|"wrong",
  "reasoning": "<brief explanation>"
}

Rules:
- "correct": At least one chunk directly and fully answers the question
- "ambiguous": Chunks are related but don't fully answer, or contain partial info
- "wrong": Chunks are irrelevant to the question"""


def _extract_json(text: str) -> dict:
    """Parse JSON from LLM output, stripping markdown code fences."""
    cleaned = text.strip()
    cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
    cleaned = re.sub(r"\s*```$", "", cleaned)
    return json.loads(cleaned.strip())


def assess_and_correct(
    question: str, evidence: list[RankedEvidence],
) -> CRAGResult:
    """Grade retrieval quality and apply corrective action.

    Returns CRAGResult with potentially modified evidence list
    and a correction note for the answer generator.
    """
    if not evidence:
        return CRAGResult(
            grade=RetrievalGrade.wrong,
            evidence=[],
            correction_note="No evidence was retrieved. Answer based on general knowledge or decline.",
        )

    # Build evidence summary for grading
    evidence_text = "\n---\n".join(
        f"[{i+1}] {e.doc_title}: {e.text[:400]}"
        for i, e in enumerate(evidence[:6])
    )

    try:
        response = chat_completion(
            system_prompt=_GRADE_PROMPT,
            user_message=f"Question: {question}\n\nEvidence:\n{evidence_text}",
            temperature=0.0,
        )
        data = _extract_json(response)
        grade = RetrievalGrade(data.get("grade", "ambiguous"))
    except Exception:
        logger.warning("CRAG grading failed, defaulting to ambiguous", exc_info=True)
        grade = RetrievalGrade.ambiguous

    # Apply corrective action based on grade
    if grade == RetrievalGrade.correct:
        logger.info("[crag] Grade=correct — using evidence as-is")
        return CRAGResult(grade=grade, evidence=evidence)

    if grade == RetrievalGrade.ambiguous:
        logger.info("[crag] Grade=ambiguous — keeping evidence with caveat")
        return CRAGResult(
            grade=grade,
            evidence=evidence,
            correction_note=(
                "The retrieved evidence may not fully answer the question. "
                "Use it as supporting context but note any gaps or uncertainties."
            ),
        )

    # Wrong: evidence is irrelevant — strip it
    logger.info("[crag] Grade=wrong — discarding irrelevant evidence")
    return CRAGResult(
        grade=grade,
        evidence=[],
        correction_note=(
            "The retrieved documents were not relevant to this question. "
            "Answer based on your general knowledge, or indicate you cannot "
            "answer from the available documents."
        ),
    )
