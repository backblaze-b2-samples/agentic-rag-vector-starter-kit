"""Document processing pipeline — orchestrates the full ingestion flow.

Flow: chunk → classify → summarize → embed → store in LanceDB.
"""

import hashlib
import logging
from datetime import UTC, datetime

from app.repo import add_chunks, delete_doc_chunks
from app.service.chunker import chunk_document
from app.service.classifier import classify_document
from app.service.embedder import embed_chunks
from app.service.summarizer import summarize_chunk, summarize_document
from app.types import DocumentClassification, DocumentStatus, ProcessedDocument

logger = logging.getLogger(__name__)

# Content types that support text extraction and chunking
PROCESSABLE_TYPES = {
    "application/pdf",
    "text/plain",
    "text/csv",
    "text/markdown",
    "application/json",
}


def _generate_chunk_id(doc_id: str, chunk_index: int) -> str:
    """Deterministic chunk ID from doc key + index."""
    raw = f"{doc_id}::{chunk_index}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def process_document(
    file_data: bytes,
    doc_id: str,
    filename: str,
    content_type: str,
) -> ProcessedDocument:
    """Run the full document processing pipeline.

    1. Check if content type is processable
    2. Chunk the document
    3. Classify based on text sample
    4. Summarize each chunk
    5. Generate embeddings
    6. Store chunks + vectors in LanceDB

    Returns ProcessedDocument with status and metadata.
    """
    if content_type not in PROCESSABLE_TYPES:
        return ProcessedDocument(
            doc_id=doc_id,
            filename=filename,
            classification=DocumentClassification.general,
            summary=f"File type {content_type} not supported for RAG processing",
            chunk_count=0,
            total_tokens=0,
            status=DocumentStatus.completed,
            processed_at=datetime.now(UTC),
        )

    try:
        # Step 1: Chunk the document
        raw_chunks = chunk_document(file_data, content_type, filename)
        if not raw_chunks:
            return ProcessedDocument(
                doc_id=doc_id,
                filename=filename,
                classification=DocumentClassification.general,
                summary="No text content extracted",
                chunk_count=0,
                total_tokens=0,
                status=DocumentStatus.completed,
                processed_at=datetime.now(UTC),
            )

        # Step 2: Classify using first chunk's text
        all_text = " ".join(c["text"] for c in raw_chunks[:3])
        classification = classify_document(all_text)

        # Step 3: Summarize each chunk
        chunk_summaries = [summarize_chunk(c["text"]) for c in raw_chunks]

        # Step 4: Generate whole-document summary
        doc_summary = summarize_document(chunk_summaries)

        # Step 5: Embed all chunks (using text + summary for richer vectors)
        texts_to_embed = [
            f"{c['text']}\n\nSummary: {s}"
            for c, s in zip(raw_chunks, chunk_summaries, strict=True)
        ]
        vectors = embed_chunks(texts_to_embed)

        # Step 6: Build LanceDB records and store
        now = datetime.now(UTC).isoformat()
        lancedb_records = []
        total_tokens = 0
        for i, (chunk, summary, vector) in enumerate(
            zip(raw_chunks, chunk_summaries, vectors, strict=True)
        ):
            token_count = len(chunk["text"].split())  # rough word-based estimate
            total_tokens += token_count
            lancedb_records.append({
                "chunk_id": _generate_chunk_id(doc_id, i),
                "doc_id": doc_id,
                "doc_title": filename,
                "section_path": chunk["section_path"],
                "text": chunk["text"],
                "summary": summary,
                "classification": classification.value,
                "chunk_index": i,
                "total_chunks": chunk["total_chunks"],
                "source_filename": filename,
                "source_content_type": content_type,
                "source_page": chunk.get("page") or 0,
                "token_count": token_count,
                "updated_at": now,
                "vector": vector,
            })

        # Remove existing chunks then store new ones (re-upload case).
        # If add_chunks fails, the file is still in B2 and can be re-uploaded.
        delete_doc_chunks(doc_id)
        add_chunks(lancedb_records)

        logger.info(
            "Pipeline complete: %s (%d chunks, %s)",
            filename,
            len(lancedb_records),
            classification.value,
        )

        return ProcessedDocument(
            doc_id=doc_id,
            filename=filename,
            classification=classification,
            summary=doc_summary,
            chunk_count=len(lancedb_records),
            total_tokens=total_tokens,
            status=DocumentStatus.completed,
            processed_at=datetime.now(UTC),
        )

    except Exception as e:
        logger.exception("Pipeline failed for %s: %s", filename, e)
        return ProcessedDocument(
            doc_id=doc_id,
            filename=filename,
            classification=DocumentClassification.general,
            summary="",
            chunk_count=0,
            total_tokens=0,
            status=DocumentStatus.failed,
            error_message=str(e),
            processed_at=datetime.now(UTC),
        )
