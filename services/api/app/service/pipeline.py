"""Document processing pipeline — orchestrates the full ingestion flow.

Flow: chunk → classify → summarize → embed → store in LanceDB.
"""

import hashlib
import logging
from datetime import UTC, datetime

from app.config import settings
from app.repo import add_chunks, delete_doc_chunks, ensure_fts_index, log_ingestion
from app.service.chunker import chunk_document
from app.service.classifier import classify_document
from app.service.contextualizer import contextualize_chunks
from app.service.embedder import embed_chunks
from app.service.summarizer import summarize_chunk, summarize_document
from app.types import DocumentClassification, DocumentStatus, ProcessedDocument

logger = logging.getLogger(__name__)


def _safe_log_ingestion(
    doc_id: str, filename: str, status: str,
    chunk_count: int, total_tokens: int, classification: str,
    error_message: str | None, summary: str = "",
) -> None:
    """Log ingestion to SQLite for dashboard. Non-blocking on failure."""
    try:
        log_ingestion(
            doc_id=doc_id, filename=filename, status=status,
            chunk_count=chunk_count, total_tokens=total_tokens,
            classification=classification, error_message=error_message,
            summary=summary,
        )
    except Exception:
        logger.warning("Failed to log ingestion metrics", exc_info=True)


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
        strategy = settings.chunk_strategy
        logger.info("[pipeline] Step 1/6: Chunking %s (%s, strategy=%s)", filename, content_type, strategy)
        raw_chunks = chunk_document(file_data, content_type, filename, strategy=strategy)
        if not raw_chunks:
            logger.info("[pipeline] No text extracted from %s — skipping", filename)
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
        logger.info("[pipeline] Step 1 done: %d chunks from %s", len(raw_chunks), filename)

        # Step 2: Classify using first chunk's text
        logger.info("[pipeline] Step 2/6: Classifying %s", filename)
        all_text = " ".join(c["text"] for c in raw_chunks[:3])
        classification = classify_document(all_text)
        logger.info("[pipeline] Step 2 done: classified as %s", classification.value)

        # Step 3: Summarize each chunk
        logger.info("[pipeline] Step 3/6: Summarizing %d chunks", len(raw_chunks))
        chunk_summaries = [summarize_chunk(c["text"]) for c in raw_chunks]
        logger.info("[pipeline] Step 3 done: %d chunk summaries", len(chunk_summaries))

        # Step 4: Generate whole-document summary
        logger.info("[pipeline] Step 4/6: Generating document summary")
        doc_summary = summarize_document(chunk_summaries)
        logger.info("[pipeline] Step 4 done: doc summary length=%d", len(doc_summary))

        # Step 4b: Contextual chunking — prepend LLM context to each chunk
        logger.info("[pipeline] Step 4b: Contextualizing %d chunks", len(raw_chunks))
        contextualize_chunks(raw_chunks, doc_summary, filename)
        logger.info("[pipeline] Step 4b done: chunks contextualized")

        # Step 5: Embed all chunks (using contextualized text + summary)
        logger.info("[pipeline] Step 5/6: Embedding %d chunks", len(raw_chunks))
        texts_to_embed = [
            f"{c.get('text_with_context', c['text'])}\n\nSummary: {s}"
            for c, s in zip(raw_chunks, chunk_summaries, strict=True)
        ]
        vectors = embed_chunks(texts_to_embed)
        logger.info("[pipeline] Step 5 done: %d vectors generated", len(vectors))

        # Step 6: Store in LanceDB
        logger.info("[pipeline] Step 6/6: Storing %d chunks in LanceDB", len(raw_chunks))
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

        # Remove existing chunks then store new ones (re-upload case)
        delete_doc_chunks(doc_id)
        add_chunks(lancedb_records)
        # Refresh FTS index for hybrid search
        ensure_fts_index()

        logger.info(
            "[pipeline] Complete: %s — %d chunks, %d tokens, %s",
            filename, len(lancedb_records), total_tokens, classification.value,
        )

        # Log successful ingestion for dashboard
        _safe_log_ingestion(
            doc_id, filename, "completed",
            len(lancedb_records), total_tokens, classification.value, None,
            summary=doc_summary,
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
        # Log failed ingestion for dashboard
        _safe_log_ingestion(doc_id, filename, "failed", 0, 0, "general", str(e))
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
