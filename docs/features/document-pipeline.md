<!-- last_verified: 2026-03-10 -->
# Document Processing Pipeline

## Purpose

Automatically process uploaded documents into vector-searchable chunks stored in LanceDB (backed by B2).

## Flow

```
Upload completes → service/pipeline.py::process_document()
  1. chunk_document()     — split text into retrieval-sized pieces
  2. classify_document()  — LLM categorizes doc (policy, procedure, faq, etc.)
  3. summarize_chunk()    — brief summary per chunk
  4. summarize_document() — whole-doc summary from chunk summaries
  5. embed_chunks()       — generate vectors via OpenAI embeddings
  6. add_chunks()         — store in LanceDB (on B2)
```

## Supported Content Types

- `application/pdf` — text extracted per page via PyPDF2
- `text/plain` — direct UTF-8 decode
- `text/csv` — treated as plain text
- `text/markdown` — treated as plain text
- `application/json` — treated as plain text

Non-text files (images, audio, video) get uploaded to B2 but skip the pipeline.

## Chunking Strategy

- Recursive character splitting: paragraph breaks → newlines → sentences → words
- Default: 1000 chars per chunk, 200 char overlap
- Configurable via `CHUNK_SIZE`, `CHUNK_OVERLAP`, `MAX_CHUNKS_PER_DOC` env vars
- Section path detection from markdown headings or first line

## Classification

LLM-based classification into: policy, procedure, reference, tutorial, faq, troubleshooting, api_docs, general. Uses the configured LLM provider (OpenAI default, Anthropic optional). Falls back to `general` on error.

## Embedding

- Default: OpenAI `text-embedding-3-small` (1536 dimensions)
- Embeds `text + summary` per chunk for richer semantic representation
- Batched in groups of 100 to respect rate limits

## Storage

- LanceDB table: `document_chunks`
- Stored on B2 via S3-compatible URI at `s3://{bucket}/lancedb/`
- Re-upload of same file replaces existing chunks (idempotent)

## API Endpoints

| Method | Endpoint | Purpose |
|--------|----------|---------|
| GET | `/documents/stats` | Vector store stats (total chunks) |
| GET | `/documents/{doc_id}/chunks` | All chunks for a document |
| GET | `/documents/search?q=...&k=10` | Semantic search across chunks |

## Error Handling

- Pipeline failures don't block the upload response
- Failed documents get `status: "failed"` with `error_message`
- Individual step failures degrade gracefully (e.g., classification falls back to "general")

## Tests

- `tests/test_chunker.py` — splitting, section detection, max chunk enforcement
- `tests/test_classifier.py` — LLM classification, fallbacks, input truncation
- `tests/test_pipeline.py` — end-to-end pipeline, error handling, chunk ID generation
- `tests/test_structure.py` — lancedb/langchain SDK isolation in repo/
