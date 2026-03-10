"""LanceDB repo layer — vector store operations backed by B2 storage.

All lancedb SDK usage is confined to this module.
"""

import functools
import logging
import re
from datetime import UTC, datetime

import lancedb
import pyarrow as pa

from app.config import settings

logger = logging.getLogger(__name__)

# Schema for the document_chunks table
CHUNKS_TABLE = "document_chunks"
EMBEDDING_DIM = 1536  # text-embedding-3-small default

CHUNKS_SCHEMA = pa.schema([
    pa.field("chunk_id", pa.string()),
    pa.field("doc_id", pa.string()),
    pa.field("doc_title", pa.string()),
    pa.field("section_path", pa.string()),
    pa.field("text", pa.string()),
    pa.field("summary", pa.string()),
    pa.field("classification", pa.string()),
    pa.field("chunk_index", pa.int32()),
    pa.field("total_chunks", pa.int32()),
    pa.field("source_filename", pa.string()),
    pa.field("source_content_type", pa.string()),
    pa.field("source_page", pa.int32()),
    pa.field("token_count", pa.int32()),
    pa.field("updated_at", pa.string()),
    pa.field("vector", pa.list_(pa.float32(), EMBEDDING_DIM)),
])


# Only allow safe characters in WHERE clause values to prevent injection
_SAFE_VALUE_RE = re.compile(r"^[a-zA-Z0-9_\-./: ]+$")
_SAFE_FIELD_RE = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]*$")


def _sanitize_where_value(value: str) -> str:
    """Escape single quotes and validate WHERE clause values."""
    if not _SAFE_VALUE_RE.match(value):
        raise ValueError("Filter value contains unsafe characters")
    return value.replace("'", "''")


def _sanitize_field_name(field: str) -> str:
    """Validate field names are alphanumeric identifiers."""
    if not _SAFE_FIELD_RE.match(field):
        raise ValueError(f"Unsafe field name for WHERE clause: {field!r}")
    return field


@functools.lru_cache(maxsize=1)
def get_db():
    """Connect to LanceDB using configured URI (S3/B2 or local)."""
    uri = settings.lancedb_storage_uri
    logger.info("Connecting to LanceDB", extra={"uri": uri})
    return lancedb.connect(uri)


def ensure_table_exists() -> None:
    """Create the chunks table if it doesn't exist."""
    db = get_db()
    existing = db.table_names()
    if CHUNKS_TABLE not in existing:
        db.create_table(CHUNKS_TABLE, schema=CHUNKS_SCHEMA)
        logger.info("Created LanceDB table", extra={"table": CHUNKS_TABLE})


def add_chunks(chunks: list[dict]) -> int:
    """Insert document chunks with embeddings into LanceDB.

    Each dict must have all CHUNKS_SCHEMA fields including 'vector'.
    Returns number of chunks inserted.
    """
    if not chunks:
        return 0
    db = get_db()
    ensure_table_exists()
    table = db.open_table(CHUNKS_TABLE)
    table.add(chunks)
    logger.info("Added chunks to LanceDB", extra={"count": len(chunks)})
    return len(chunks)


def search_vectors(
    query_vector: list[float], k: int = 20, filters: dict | None = None
) -> list[dict]:
    """Run kNN vector search on document chunks.

    Returns list of dicts with chunk fields + _distance score.
    """
    db = get_db()
    ensure_table_exists()
    table = db.open_table(CHUNKS_TABLE)

    query = table.search(query_vector).limit(k)

    # Apply optional metadata filters (sanitized to prevent injection)
    if filters:
        where_clauses = []
        for field, value in filters.items():
            safe_field = _sanitize_field_name(field)
            safe_value = _sanitize_where_value(str(value))
            where_clauses.append(f"{safe_field} = '{safe_value}'")
        if where_clauses:
            query = query.where(" AND ".join(where_clauses))

    results = query.to_list()
    return results


def get_chunks_by_doc(doc_id: str) -> list[dict]:
    """Retrieve all chunks for a specific document."""
    safe_id = _sanitize_where_value(doc_id)
    db = get_db()
    ensure_table_exists()
    table = db.open_table(CHUNKS_TABLE)
    results = table.search().where(f"doc_id = '{safe_id}'").limit(10000).to_list()
    # Sort by chunk_index
    results.sort(key=lambda c: c.get("chunk_index", 0))
    return results


def delete_doc_chunks(doc_id: str) -> int:
    """Delete all chunks for a document. Returns count deleted."""
    safe_id = _sanitize_where_value(doc_id)
    db = get_db()
    ensure_table_exists()
    table = db.open_table(CHUNKS_TABLE)
    # Get count before delete
    existing = table.search().where(f"doc_id = '{safe_id}'").limit(10000).to_list()
    count = len(existing)
    if count > 0:
        table.delete(f"doc_id = '{safe_id}'")
        logger.info("Deleted chunks", extra={"doc_id": doc_id, "count": count})
    return count


def get_table_stats() -> dict:
    """Return basic stats about the chunks table."""
    db = get_db()
    ensure_table_exists()
    table = db.open_table(CHUNKS_TABLE)
    row_count = table.count_rows()
    return {
        "total_chunks": row_count,
        "table": CHUNKS_TABLE,
        "updated_at": datetime.now(UTC).isoformat(),
    }
