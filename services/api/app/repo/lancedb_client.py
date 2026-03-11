"""LanceDB repo layer — vector store operations backed by B2 storage.

All lancedb SDK usage is confined to this module.
"""

import functools
import logging
import os
import re
from datetime import UTC, datetime

import lancedb
import pyarrow as pa

from app.config import settings

logger = logging.getLogger(__name__)

# LanceDB reads AWS_* env vars for S3 auth. Map B2 credentials so lance can
# connect to B2's S3-compatible API. AWS_S3_ALLOW_UNSAFE_RENAME bypasses
# conditional PUTs (If-None-Match) which B2 does not support.
if settings.b2_application_key_id and not os.environ.get("AWS_ACCESS_KEY_ID"):
    os.environ["AWS_ACCESS_KEY_ID"] = settings.b2_application_key_id
    os.environ["AWS_SECRET_ACCESS_KEY"] = settings.b2_application_key
    os.environ["AWS_DEFAULT_REGION"] = settings.b2_s3_endpoint.split("//s3.")[1].split(".")[0] if "//s3." in settings.b2_s3_endpoint else "us-west-004"
    os.environ["AWS_ENDPOINT_URL"] = settings.b2_s3_endpoint
    os.environ["AWS_S3_ALLOW_UNSAFE_RENAME"] = "true"
    logger.info(
        "B2→AWS env mapped: region=%s endpoint=%s",
        os.environ["AWS_DEFAULT_REGION"], os.environ["AWS_ENDPOINT_URL"],
    )

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


def _table_exists() -> bool:
    """Check if the chunks table exists in LanceDB."""
    db = get_db()
    return CHUNKS_TABLE in db.table_names()


@functools.lru_cache(maxsize=1)
def get_db():
    """Connect to LanceDB using configured URI (S3/B2 or local)."""
    uri = settings.lancedb_storage_uri
    logger.info("Connecting to LanceDB at %s", uri)
    db = lancedb.connect(uri)
    tables = db.table_names()
    logger.info("LanceDB connected, existing tables: %s", tables)
    return db


def ensure_tables_ready() -> None:
    """Startup check: ensure the chunks table exists and is accessible.

    On S3/B2 backends, empty-schema tables can be left in a broken state.
    This function verifies the table is usable, drops it if corrupt, and
    recreates it with the correct schema + a seed row (then deletes the row).
    """
    db = get_db()
    if CHUNKS_TABLE in db.table_names():
        # Table exists — verify we can actually open and read it
        try:
            table = db.open_table(CHUNKS_TABLE)
            table.count_rows()
            logger.info("LanceDB table '%s' is ready", CHUNKS_TABLE)
            return
        except Exception:
            logger.warning(
                "LanceDB table '%s' exists but is broken — dropping and recreating",
                CHUNKS_TABLE, exc_info=True,
            )
            db.drop_table(CHUNKS_TABLE)

    # Create table with a seed row (empty-schema creates don't persist on S3)
    logger.info("Creating LanceDB table '%s' with seed data", CHUNKS_TABLE)
    seed = pa.table(
        {
            "chunk_id": ["__seed__"],
            "doc_id": ["__seed__"],
            "doc_title": [""],
            "section_path": [""],
            "text": [""],
            "summary": [""],
            "classification": ["general"],
            "chunk_index": pa.array([0], type=pa.int32()),
            "total_chunks": pa.array([0], type=pa.int32()),
            "source_filename": [""],
            "source_content_type": [""],
            "source_page": pa.array([0], type=pa.int32()),
            "token_count": pa.array([0], type=pa.int32()),
            "updated_at": [""],
            "vector": [([0.0] * EMBEDDING_DIM)],
        },
        schema=CHUNKS_SCHEMA,
    )
    table = db.create_table(CHUNKS_TABLE, seed)
    # Remove the seed row so the table is empty but structurally valid
    table.delete("chunk_id = '__seed__'")
    # Verify it's accessible
    count = table.count_rows()
    logger.info("LanceDB table '%s' created and verified (rows=%d)", CHUNKS_TABLE, count)


def add_chunks(chunks: list[dict]) -> int:
    """Insert document chunks with embeddings into LanceDB.

    Creates the table on first insert (empty-schema tables don't persist
    reliably on S3 backends like B2). Returns number of chunks inserted.
    """
    if not chunks:
        return 0
    db = get_db()
    if _table_exists():
        table = db.open_table(CHUNKS_TABLE)
        table.add(chunks)
    else:
        # First insert — create table with data (works reliably on S3/B2)
        logger.info("Creating LanceDB table with first %d chunks", len(chunks))
        db.create_table(CHUNKS_TABLE, chunks)
    logger.info("Stored %d chunks in LanceDB", len(chunks))
    return len(chunks)


def search_vectors(
    query_vector: list[float], k: int = 20, filters: dict | None = None
) -> list[dict]:
    """Run kNN vector search on document chunks."""
    if not _table_exists():
        logger.info("No chunks table yet — returning empty search results")
        return []
    db = get_db()
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

    return query.to_list()


def get_chunks_by_doc(doc_id: str) -> list[dict]:
    """Retrieve all chunks for a specific document."""
    if not _table_exists():
        return []
    safe_id = _sanitize_where_value(doc_id)
    db = get_db()
    table = db.open_table(CHUNKS_TABLE)
    results = table.search().where(f"doc_id = '{safe_id}'").limit(10000).to_list()
    results.sort(key=lambda c: c.get("chunk_index", 0))
    return results


def delete_doc_chunks(doc_id: str) -> int:
    """Delete all chunks for a document. Returns count deleted."""
    if not _table_exists():
        return 0
    safe_id = _sanitize_where_value(doc_id)
    db = get_db()
    table = db.open_table(CHUNKS_TABLE)
    existing = table.search().where(f"doc_id = '{safe_id}'").limit(10000).to_list()
    count = len(existing)
    if count > 0:
        table.delete(f"doc_id = '{safe_id}'")
        logger.info("Deleted %d chunks for doc_id=%s", count, doc_id)
    return count


def get_table_stats() -> dict:
    """Return basic stats about the chunks table."""
    if not _table_exists():
        return {
            "total_chunks": 0,
            "table": CHUNKS_TABLE,
            "updated_at": datetime.now(UTC).isoformat(),
        }
    db = get_db()
    table = db.open_table(CHUNKS_TABLE)
    row_count = table.count_rows()
    return {
        "total_chunks": row_count,
        "table": CHUNKS_TABLE,
        "updated_at": datetime.now(UTC).isoformat(),
    }


def ensure_fts_index() -> None:
    """Create full-text search index on the text column if not present.

    Required for hybrid (BM25 + dense vector) search. Safe to call repeatedly.
    """
    if not _table_exists():
        return
    db = get_db()
    table = db.open_table(CHUNKS_TABLE)
    if table.count_rows() == 0:
        return
    try:
        table.create_fts_index("text", replace=True)
        logger.info("FTS index created/refreshed on '%s.text'", CHUNKS_TABLE)
    except Exception:
        logger.warning("FTS index creation failed (non-critical)", exc_info=True)


def search_hybrid(
    query: str, query_vector: list[float], k: int = 20,
    filters: dict | None = None,
) -> list[dict]:
    """Hybrid search combining BM25 full-text + dense vector via RRF.

    Falls back to pure vector search if FTS is unavailable.
    """
    if not _table_exists():
        return []
    db = get_db()
    table = db.open_table(CHUNKS_TABLE)
    try:
        # LanceDB 0.20 hybrid: pass text query to search(), vector via .vector()
        query_builder = (
            table.search(query, query_type="hybrid")
            .vector(query_vector)
            .limit(k)
        )
        if filters:
            clauses = []
            for field, value in filters.items():
                safe_f = _sanitize_field_name(field)
                safe_v = _sanitize_where_value(str(value))
                clauses.append(f"{safe_f} = '{safe_v}'")
            if clauses:
                query_builder = query_builder.where(" AND ".join(clauses))
        results = query_builder.to_list()
        logger.debug("Hybrid search returned %d results", len(results))
        return results
    except Exception:
        logger.warning("Hybrid search failed, falling back to vector", exc_info=True)
        return search_vectors(query_vector, k=k, filters=filters)


def check_lancedb_connectivity() -> bool:
    """Check if LanceDB is reachable by listing tables."""
    try:
        db = get_db()
        db.table_names()
        return True
    except Exception:
        logger.warning("LanceDB connectivity check failed", exc_info=True)
        return False
