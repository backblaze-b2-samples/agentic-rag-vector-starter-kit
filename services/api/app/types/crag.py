"""Types for Corrective RAG (CRAG) module."""

from enum import StrEnum

from pydantic import BaseModel

from app.types.retrieval import RankedEvidence


class RetrievalGrade(StrEnum):
    """Grading of retrieval quality for CRAG."""
    correct = "correct"      # Evidence clearly answers the question
    ambiguous = "ambiguous"  # Partial or unclear evidence
    wrong = "wrong"          # Evidence is irrelevant to the question


class CRAGResult(BaseModel):
    """Result of CRAG assessment and correction."""
    grade: RetrievalGrade
    evidence: list[RankedEvidence]
    correction_note: str = ""  # Guidance for the answer generator
