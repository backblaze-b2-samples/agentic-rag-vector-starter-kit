"""Document service — search, chunk retrieval, and stats."""

from app.repo import generate_query_embedding, get_chunks_by_doc, get_table_stats, search_vectors


def get_document_chunks(doc_id: str) -> list[dict]:
    """Get all chunks for a document, stripped of vector data."""
    chunks = get_chunks_by_doc(doc_id)
    for chunk in chunks:
        chunk.pop("vector", None)
    return chunks


def search_documents(query: str, k: int = 10) -> list[dict]:
    """Semantic search across all document chunks."""
    query_vector = generate_query_embedding(query)
    results = search_vectors(query_vector, k=k)
    for r in results:
        r.pop("vector", None)
    return results


def get_document_stats() -> dict:
    """Return vector store statistics."""
    return get_table_stats()
