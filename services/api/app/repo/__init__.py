from app.repo.b2_client import (
    check_connectivity,
    delete_file,
    get_file_metadata,
    get_presigned_url,
    get_upload_stats,
    list_files,
    upload_file,
)
from app.repo.corpus_index import get_corpus_index
from app.repo.cross_encoder_client import score_pairs
from app.repo.lancedb_client import (
    add_chunks,
    check_lancedb_connectivity,
    delete_doc_chunks,
    ensure_fts_index,
    ensure_tables_ready,
    get_chunks_by_doc,
    get_table_stats,
    search_hybrid,
    search_vectors,
)
from app.repo.llm_client import (
    chat_completion,
    chat_completion_stream,
    generate_embeddings,
    generate_query_embedding,
)
from app.repo.query_log import (
    get_agent_behavior,
    get_last_ingestion_ts,
    get_query_stats,
    get_recent_ingestions,
    get_recent_queries,
    get_retrieval_quality,
    log_ingestion,
    log_query,
    update_eval_scores,
)
from app.repo.session_analytics import (
    get_session_messages_with_eval,
    get_sessions_with_ragas,
)

__all__ = [
    "add_chunks",
    "chat_completion",
    "chat_completion_stream",
    "check_connectivity",
    "check_lancedb_connectivity",
    "delete_doc_chunks",
    "delete_file",
    "ensure_fts_index",
    "ensure_tables_ready",
    "generate_embeddings",
    "generate_query_embedding",
    "get_agent_behavior",
    "get_chunks_by_doc",
    "get_corpus_index",
    "get_file_metadata",
    "get_last_ingestion_ts",
    "get_presigned_url",
    "get_query_stats",
    "get_recent_ingestions",
    "get_recent_queries",
    "get_retrieval_quality",
    "get_session_messages_with_eval",
    "get_sessions_with_ragas",
    "get_table_stats",
    "get_upload_stats",
    "list_files",
    "log_ingestion",
    "log_query",
    "score_pairs",
    "search_hybrid",
    "search_vectors",
    "update_eval_scores",
    "upload_file",
]
