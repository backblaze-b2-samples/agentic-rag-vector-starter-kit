"""Types for document processing pipeline."""

from datetime import datetime
from enum import Enum

from pydantic import BaseModel


class DocumentStatus(str, Enum):
    """Processing pipeline status."""
    pending = "pending"
    processing = "processing"
    completed = "completed"
    failed = "failed"


class DocumentClassification(str, Enum):
    """High-level document category for retrieval routing."""
    policy = "policy"
    procedure = "procedure"
    reference = "reference"
    tutorial = "tutorial"
    faq = "faq"
    troubleshooting = "troubleshooting"
    api_docs = "api_docs"
    general = "general"


class DocumentChunk(BaseModel):
    """A single chunk of a processed document, stored in LanceDB."""
    chunk_id: str
    doc_id: str  # B2 object key
    doc_title: str
    section_path: str  # e.g. "Chapter 2 > Setup > Prerequisites"
    text: str
    summary: str = ""
    classification: DocumentClassification = DocumentClassification.general
    chunk_index: int  # position in document
    total_chunks: int
    # Source provenance
    source_filename: str
    source_content_type: str
    source_page: int | None = None  # for PDFs
    # Metadata
    token_count: int = 0
    updated_at: datetime | None = None


class ProcessedDocument(BaseModel):
    """Result of the full document processing pipeline."""
    doc_id: str  # B2 object key
    filename: str
    classification: DocumentClassification
    summary: str  # whole-document summary
    chunk_count: int
    total_tokens: int
    status: DocumentStatus
    error_message: str | None = None
    processed_at: datetime | None = None


class ProcessingStatusResponse(BaseModel):
    """API response for document processing status."""
    doc_id: str
    filename: str
    status: DocumentStatus
    chunk_count: int = 0
    classification: str = ""
    summary: str = ""
    error_message: str | None = None
