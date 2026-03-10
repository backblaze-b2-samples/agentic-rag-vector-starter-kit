"""Document processing endpoints — status, chunks, and search."""

import logging

from fastapi import APIRouter, HTTPException

from app.service.documents import get_document_chunks, get_document_stats, search_documents

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/documents", tags=["documents"])


@router.get("/stats")
async def document_stats():
    """Get vector store statistics."""
    try:
        return get_document_stats()
    except Exception:
        logger.exception("Failed to get document stats")
        raise HTTPException(status_code=503, detail="Vector store unavailable") from None


@router.get("/{doc_id:path}/chunks")
async def get_chunks_endpoint(doc_id: str):
    """Get all chunks for a specific document."""
    if not doc_id:
        raise HTTPException(status_code=400, detail="doc_id required")
    try:
        chunks = get_document_chunks(doc_id)
    except Exception:
        logger.exception("Failed to get chunks for %s", doc_id)
        raise HTTPException(status_code=503, detail="Vector store unavailable") from None
    return {"doc_id": doc_id, "chunks": chunks, "count": len(chunks)}


@router.get("/search")
async def search_endpoint(q: str, k: int = 10):
    """Semantic search across all document chunks."""
    if not q.strip():
        raise HTTPException(status_code=400, detail="Query required")
    if k < 1 or k > 100:
        raise HTTPException(status_code=400, detail="k must be between 1 and 100")
    try:
        results = search_documents(q, k=k)
    except Exception:
        logger.exception("Search failed for query")
        raise HTTPException(status_code=503, detail="Search service unavailable") from None
    return {"query": q, "results": results, "count": len(results)}
