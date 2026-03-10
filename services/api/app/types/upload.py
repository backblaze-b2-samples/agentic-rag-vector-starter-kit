from datetime import datetime

from pydantic import BaseModel

from app.types.files import FileMetadataDetail


class PipelineResult(BaseModel):
    """Summary of RAG pipeline processing returned with upload response."""
    status: str  # "completed" | "failed" | "skipped"
    classification: str = ""
    summary: str = ""
    chunk_count: int = 0
    total_tokens: int = 0
    error_message: str | None = None


class FileUploadResponse(BaseModel):
    key: str
    filename: str
    size_bytes: int
    size_human: str
    content_type: str
    uploaded_at: datetime
    url: str | None = None
    metadata: FileMetadataDetail | None = None
    pipeline: PipelineResult | None = None
