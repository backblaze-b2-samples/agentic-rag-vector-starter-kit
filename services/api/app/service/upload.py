import logging
import re

from app.config import settings
from app.repo import upload_file
from app.service.metadata import extract_metadata
from app.service.pipeline import process_document, process_document_with_steps
from app.types import FileUploadResponse, PipelineResult
from app.types.formatting import humanize_bytes

logger = logging.getLogger(__name__)

ALLOWED_TYPES = {
    "image/jpeg",
    "image/png",
    "image/gif",
    "image/webp",
    "application/pdf",
    "text/plain",
    "text/csv",
    "text/markdown",
    "application/json",
    "application/zip",
    "video/mp4",
    "audio/mpeg",
    "audio/wav",
    "image/svg+xml",
}

MIME_EXTENSION_MAP: dict[str, set[str]] = {
    "image/jpeg": {"jpg", "jpeg", "jfif"},
    "image/png": {"png"},
    "image/gif": {"gif"},
    "image/webp": {"webp"},
    "application/pdf": {"pdf"},
    "text/plain": {"txt", "text", "log"},
    "text/markdown": {"md", "markdown"},
    "text/csv": {"csv"},
    "application/json": {"json"},
    "application/zip": {"zip"},
    "video/mp4": {"mp4"},
    "audio/mpeg": {"mp3", "mpeg"},
    "audio/wav": {"wav"},
    "image/svg+xml": {"svg"},
}

_SAFE_FILENAME_RE = re.compile(r"[^\w\-.]")


def sanitize_filename(filename: str) -> str:
    """Sanitize filename: strip path components, remove unsafe chars, limit length."""
    name = filename.replace("\\", "/").split("/")[-1]
    name = name.replace("\x00", "")
    name = _SAFE_FILENAME_RE.sub("_", name)
    name = re.sub(r"[_.]{2,}", "_", name)
    name = name.lstrip(".").strip()
    if len(name) > 200:
        base, _, ext = name.rpartition(".")
        name = base[: 200 - len(ext) - 1] + "." + ext if ext else name[:200]
    return name or "unnamed"


def validate_extension_matches_type(filename: str, content_type: str) -> bool:
    """Verify the file extension is consistent with the declared MIME type."""
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    allowed_exts = MIME_EXTENSION_MAP.get(content_type)
    if allowed_exts is None:
        return False
    if not ext:
        return True
    return ext in allowed_exts


class UploadError(Exception):
    """Raised when upload validation fails."""

    def __init__(self, detail: str, status_code: int = 400):
        self.detail = detail
        self.status_code = status_code
        super().__init__(detail)


def _validate_upload(
    file_data: bytes, filename: str, content_type: str, content_length: int | None,
) -> str:
    """Validate upload params. Returns sanitized filename. Raises UploadError."""
    if not filename:
        raise UploadError("No filename provided")
    if content_length and content_length > settings.max_file_size:
        raise UploadError(f"File too large. Max size: {humanize_bytes(settings.max_file_size)}", 413)
    if content_type not in ALLOWED_TYPES:
        raise UploadError(f"File type '{content_type}' not allowed", 415)
    safe_name = sanitize_filename(filename)
    if not validate_extension_matches_type(safe_name, content_type):
        raise UploadError("File extension does not match declared content type", 415)
    if len(file_data) == 0:
        raise UploadError("Empty file")
    if len(file_data) > settings.max_file_size:
        raise UploadError(f"File too large. Max size: {humanize_bytes(settings.max_file_size)}", 413)
    return safe_name


def process_upload(
    file_data: bytes,
    filename: str,
    content_type: str,
    content_length: int | None = None,
) -> FileUploadResponse:
    """Validate and process a file upload. Raises UploadError on failure."""
    safe_name = _validate_upload(file_data, filename, content_type, content_length)
    key = f"uploads/{safe_name}"
    result = upload_file(file_data, key, content_type)
    metadata = extract_metadata(file_data, safe_name, content_type)

    # Trigger RAG pipeline (chunking, classification, embedding, vector storage)
    pipeline_info: PipelineResult | None = None
    try:
        doc = process_document(file_data, key, safe_name, content_type)
        pipeline_info = PipelineResult(
            status=doc.status.value, classification=doc.classification.value,
            summary=doc.summary, chunk_count=doc.chunk_count,
            total_tokens=doc.total_tokens, error_message=doc.error_message,
        )
    except Exception:
        pipeline_info = PipelineResult(status="failed", error_message="Pipeline error")
        logger.warning("Pipeline failed for %s", key, exc_info=True)

    return FileUploadResponse(
        key=result.key, filename=result.filename, size_bytes=result.size_bytes,
        size_human=result.size_human, content_type=content_type,
        uploaded_at=result.uploaded_at, url=result.url,
        metadata=metadata, pipeline=pipeline_info,
    )


def process_upload_streaming(
    file_data: bytes, filename: str, content_type: str,
    content_length: int | None = None,
):
    """Upload file to B2, then stream pipeline step events. Yields SSE strings."""
    import json

    safe_name = _validate_upload(file_data, filename, content_type, content_length)
    key = f"uploads/{safe_name}"

    # Phase 1: upload to B2
    result = upload_file(file_data, key, content_type)
    extract_metadata(file_data, safe_name, content_type)
    yield f"data: {json.dumps({'type': 'uploaded', 'key': result.key, 'filename': result.filename})}\n\n"

    # Phase 2: stream pipeline steps
    final_doc = None
    for item in process_document_with_steps(file_data, key, safe_name, content_type):
        if item[0] == "step":
            yield f"data: {json.dumps({'type': 'step', 'label': item[1], 'status': item[2]})}\n\n"
        elif item[0] == "result":
            final_doc = item[1]

    # Phase 3: final result
    pipeline_info = None
    if final_doc:
        pipeline_info = {
            "status": final_doc.status.value, "classification": final_doc.classification.value,
            "summary": final_doc.summary, "chunk_count": final_doc.chunk_count,
            "total_tokens": final_doc.total_tokens, "error_message": final_doc.error_message,
        }
    yield f"data: {json.dumps({'type': 'done', 'key': result.key, 'filename': result.filename, 'size_bytes': result.size_bytes, 'size_human': result.size_human, 'content_type': content_type, 'uploaded_at': result.uploaded_at, 'pipeline': pipeline_info})}\n\n"
