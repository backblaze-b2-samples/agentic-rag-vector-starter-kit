"""Document chunking — split documents into retrieval-sized pieces."""

import io
import logging
import re

from app.config import settings

logger = logging.getLogger(__name__)


def _extract_text_from_pdf(file_data: bytes) -> list[dict]:
    """Extract text per page from a PDF. Returns [{page: int, text: str}]."""
    from PyPDF2 import PdfReader

    reader = PdfReader(io.BytesIO(file_data))
    pages = []
    for i, page in enumerate(reader.pages):
        text = page.extract_text() or ""
        if text.strip():
            pages.append({"page": i + 1, "text": text})
    return pages


def _extract_text_from_plain(file_data: bytes) -> list[dict]:
    """Extract text from plain text/CSV/JSON files."""
    text = file_data.decode("utf-8", errors="replace")
    return [{"page": None, "text": text}]


def _hard_split(text: str, size: int, overlap: int) -> list[str]:
    """Hard split by character limit when no separator works."""
    chunks: list[str] = []
    step = max(size - overlap, 1)
    for i in range(0, len(text), step):
        chunk = text[i : i + size]
        if chunk.strip():
            chunks.append(chunk.strip())
    return chunks


def _split_text(
    text: str,
    chunk_size: int | None = None,
    chunk_overlap: int | None = None,
) -> list[str]:
    """Recursive character text splitting with overlap.

    Splits on paragraph breaks first, then sentences, then words.
    Falls back to hard character split for oversized segments.
    """
    size = chunk_size or settings.chunk_size
    overlap = chunk_overlap or settings.chunk_overlap

    if len(text) <= size:
        return [text] if text.strip() else []

    # Try splitting by decreasing granularity
    separators = ["\n\n", "\n", ". ", " "]
    chunks: list[str] = []
    current = ""

    for sep in separators:
        parts = text.split(sep)
        if len(parts) <= 1:
            continue

        for part in parts:
            candidate = current + sep + part if current else part
            if len(candidate) <= size:
                current = candidate
            else:
                if current.strip():
                    # Hard-split oversized accumulated text
                    if len(current) > size:
                        chunks.extend(_hard_split(current, size, overlap))
                    else:
                        chunks.append(current.strip())
                # Overlap: keep tail of previous chunk
                if overlap > 0 and current:
                    tail = current[-overlap:]
                    current = tail + sep + part
                else:
                    current = part
        # Flush remaining
        if current.strip():
            if len(current) > size:
                chunks.extend(_hard_split(current, size, overlap))
            else:
                chunks.append(current.strip())
        return chunks

    # Fallback: hard split by character limit
    return _hard_split(text, size, overlap)


def _detect_section_path(text: str, chunk_index: int) -> str:
    """Extract section heading from chunk text if present."""
    # Look for markdown-style headings
    match = re.search(r"^(#{1,4})\s+(.+)$", text, re.MULTILINE)
    if match:
        return match.group(2).strip()
    # Look for title-case lines at start
    first_line = text.split("\n")[0].strip()
    if first_line and len(first_line) < 100 and first_line[0].isupper():
        return first_line
    return f"Chunk {chunk_index + 1}"


def chunk_document(
    file_data: bytes,
    content_type: str,
    filename: str,
) -> list[dict]:
    """Split a document into chunks with metadata.

    Returns list of dicts with: text, page, section_path, chunk_index.
    Respects MAX_CHUNKS_PER_DOC limit from settings.
    """
    # Extract raw text by content type
    if content_type == "application/pdf":
        pages = _extract_text_from_pdf(file_data)
    elif content_type in ("text/plain", "text/csv", "application/json", "text/markdown"):
        pages = _extract_text_from_plain(file_data)
    else:
        logger.info("Skipping chunking for unsupported type: %s", content_type)
        return []

    chunks: list[dict] = []
    for page_info in pages:
        page_chunks = _split_text(page_info["text"])
        for text in page_chunks:
            chunks.append({
                "text": text,
                "page": page_info["page"],
                "section_path": _detect_section_path(text, len(chunks)),
                "chunk_index": len(chunks),
            })

    # Enforce max chunks limit
    if len(chunks) > settings.max_chunks_per_doc:
        logger.warning(
            "Truncating chunks: %d -> %d for %s",
            len(chunks),
            settings.max_chunks_per_doc,
            filename,
        )
        chunks = chunks[: settings.max_chunks_per_doc]

    # Set total_chunks on each
    total = len(chunks)
    for chunk in chunks:
        chunk["total_chunks"] = total

    logger.info("Chunked %s into %d pieces", filename, total)
    return chunks
