"""Corpus index — lightweight document inventory for query rewriting.

Returns a list of doc titles + summaries from LanceDB so the retrieval
pipeline can rewrite queries to match corpus vocabulary.
"""

import logging
import time

from app.repo.lancedb_client import CHUNKS_TABLE, _table_exists, get_db

logger = logging.getLogger(__name__)

# Simple TTL cache (avoid querying LanceDB every chat message)
_cache: dict = {"entries": None, "ts": 0.0}
_CACHE_TTL = 300  # 5 minutes


def get_corpus_index() -> list[dict]:
    """Fetch distinct documents from the chunks table.

    Returns lightweight entries: doc_id, doc_title, classification, summary.
    Cached for 5 minutes.
    """
    now = time.monotonic()
    if _cache["entries"] is not None and (now - _cache["ts"]) < _CACHE_TTL:
        return _cache["entries"]

    if not _table_exists():
        return []

    try:
        db = get_db()
        table = db.open_table(CHUNKS_TABLE)
        # Fetch chunk_index=0 rows (one per doc) to get title + summary
        rows = (
            table.search()
            .where("chunk_index = 0")
            .limit(200)
            .to_list()
        )
        # Deduplicate by doc_id
        seen: set[str] = set()
        entries: list[dict] = []
        for r in rows:
            did = r["doc_id"]
            if did in seen:
                continue
            seen.add(did)
            entries.append({
                "doc_id": did,
                "doc_title": r.get("doc_title", ""),
                "classification": r.get("classification", "general"),
                "summary": r.get("summary", ""),
            })

        _cache["entries"] = entries
        _cache["ts"] = now
        logger.info("Corpus index refreshed: %d documents", len(entries))
        return entries

    except Exception:
        logger.warning("Failed to fetch corpus index", exc_info=True)
        return _cache["entries"] or []
