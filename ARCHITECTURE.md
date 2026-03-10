<!-- last_verified: 2026-03-10 -->
# Architecture

## Components

- **apps/web/** — Next.js 16 frontend (App Router, Tailwind v4, shadcn/ui)
  - Dashboard with stats, upload chart, recent uploads
  - Chat UI with streaming responses and source citations
  - File upload with drag-and-drop, progress tracking, RAG processing status
  - File browser with preview, download, delete
  - Dark mode via `next-themes`
- **services/api/** — FastAPI backend (layered architecture)
  - REST API for file upload, listing, deletion
  - Document processing pipeline (chunking, classification, summarization, embedding)
  - Agentic RAG retrieval engine (9-step pipeline)
  - Chat endpoints with SSE streaming
  - B2 S3 integration via boto3
  - LanceDB vector store (backed by B2)
  - LangChain LLM/embedding integration
  - File metadata extraction (images, PDFs)
  - Health check endpoint with B2 connectivity verification
  - Structured JSON logging with request tracing
  - Prometheus-format metrics endpoint
- **packages/shared/** — TypeScript type definitions
  - Mirrors Pydantic models from the API
  - Consumed by `apps/web/` as workspace dependency

## Backend Layering

The API follows a strict layered architecture:

```
types/     Pydantic models — no logic, no imports from other layers
  |
config/    Settings (pydantic-settings) — depends only on types
  |
repo/      Data access (boto3, lancedb, langchain) — no business logic
  |
service/   Business logic — calls repo, returns types
  |
runtime/   FastAPI routes — calls service, never repo directly
```

### Layering Rules

1. Dependencies flow downward only: `types` -> `config` -> `repo` -> `service` -> `runtime`
2. No backward imports (e.g., service must not import from runtime)
3. `boto3` only allowed in `repo/` layer
4. `lancedb` only allowed in `repo/` layer
5. `langchain*` SDKs only allowed in `repo/` layer
6. All boundary data uses Pydantic models (no raw dicts across layers)
7. Each file stays under 300 lines

### Directory Structure

```
services/api/
  main.py                  App entrypoint, middleware, router registration
  app/
    types/                 Pydantic models (files, chat, documents, retrieval, etc.)
    config/                Settings loaded from environment
    repo/                  Data access layer
      b2_client.py           B2 S3 operations
      lancedb_client.py      LanceDB vector store operations
      llm_client.py          LangChain LLM/embedding wrapper
    service/               Business logic
      upload.py              File upload + pipeline trigger
      files.py               File listing, download, delete
      metadata.py            File metadata extraction
      pipeline.py            Document processing orchestrator
      chunker.py             Text splitting strategies
      classifier.py          LLM-based doc classification
      summarizer.py          Chunk + document summaries
      embedder.py            Batch embedding generation
      documents.py           Document search, chunks, stats
      retrieval.py           Agentic RAG retrieval engine
      reranker.py            LLM-based reranking + evidence validation
      chat.py                Conversation management + answer generation
    runtime/               FastAPI route handlers
      upload.py              POST /upload
      files.py               GET/DELETE /files/*
      documents.py           GET /documents/*
      chat.py                POST /chat, POST /chat/stream, GET /chat/history
      health.py              GET /health
      metrics.py             GET /metrics
  tests/                   pytest tests (structural + integration + unit)
```

## Boundary Invariants

- **No external SDK leakage**: `boto3`, `lancedb`, `langchain*` only imported in `app/repo/`. All other layers interact through the repo interface.
- **No raw dicts at boundaries**: All data crossing layer boundaries uses typed Pydantic models.
- **No mutable globals**: Configuration is read-only after init. No module-level mutable state shared between layers. Exception: `chat.py` uses an in-memory conversation store scoped to the service layer (swap for persistent store later).
- **Validated inputs**: All HTTP inputs validated by FastAPI/Pydantic. All file keys validated against prefix allowlist.

## Deployment

- **Local dev** — `pnpm dev` runs both services via `concurrently`
  - Web: `localhost:3000`
  - API: `localhost:8000`
- **Railway** — two services from the same repo
  - See `infra/railway/README.md` for configuration

## Data Stores

- **Backblaze B2** — object storage (S3-compatible API)
  - All uploaded files stored in a single bucket
  - File listing and metadata via S3 `list_objects_v2` / `head_object`
- **LanceDB on B2** — vector store
  - Document chunks with embeddings stored at `s3://{bucket}/lancedb/`
  - Uses same B2 credentials via S3-compatible URI
  - Tables: `document_chunks` (text, vectors, metadata)
- No separate application database — B2 is the sole data store

## External Services

- **Backblaze B2 S3 API** — file storage, retrieval, deletion, presigned URLs
- **Anthropic API** — chat, classification, reranking, evidence validation
- **OpenAI API** — text embeddings (configurable)

## Trust Boundaries

See [docs/SECURITY.md](docs/SECURITY.md) for full security documentation.

- **Frontend -> API** — CORS-restricted to configured origins
- **API -> B2** — authenticated via application keys, signature v4
- **API -> LLM providers** — authenticated via API keys (env vars)
- **Client -> B2** — presigned URLs for download (10-min expiry, forced attachment)

## Data Flows

- **Upload + Process**: Browser -> `POST /upload` -> API validates -> B2 upload -> metadata extraction -> pipeline (chunk -> classify -> summarize -> embed -> LanceDB) -> response
- **Chat**: Browser -> `POST /chat/stream` -> intent classification -> query planning -> vector search -> RRF fusion -> LLM reranking -> evidence validation -> grounded answer generation (SSE) -> response with citations
- **List**: Browser -> `GET /files` -> service calls repo -> returns file list
- **Download**: Browser -> `GET /files/{key}/download` -> service validates key -> repo generates presigned URL -> browser downloads
- **Delete**: Browser -> `DELETE /files/{key}` -> service validates key -> repo deletes from B2
- **Search**: Browser -> `GET /documents/search?q=...` -> embedding -> vector search -> results

## Observability

- Structured JSON logging on all requests with `request_id`
- Request timing middleware (logs duration per request)
- `/metrics` endpoint (Prometheus format: request count, latency, upload count)
- `/health` endpoint (B2 connectivity check)
- Retrieval metrics logged per chat request (route, queries, candidates, latency)

## Canonical Files

- Layered API handler: `services/api/app/runtime/upload.py`
- Service orchestration: `services/api/app/service/upload.py`
- B2 data access (repo layer): `services/api/app/repo/b2_client.py`
- LanceDB vector ops: `services/api/app/repo/lancedb_client.py`
- LLM/embedding wrapper: `services/api/app/repo/llm_client.py`
- Document pipeline: `services/api/app/service/pipeline.py`
- Agentic retrieval: `services/api/app/service/retrieval.py`
- Chat service: `services/api/app/service/chat.py`
- Pydantic models: `services/api/app/types/` (files, chat, documents, retrieval, etc.)
- Config (pydantic-settings): `services/api/app/config/settings.py`
- Structural tests: `services/api/tests/test_structure.py`
- Frontend API client: `apps/web/src/lib/api-client.ts`
- Shared TypeScript types: `packages/shared/src/types.ts`

## Core Features

- [File Upload](docs/features/file-upload.md)
- [File Browser](docs/features/file-browser.md)
- [Dashboard](docs/features/dashboard.md)
- [Metadata Extraction](docs/features/metadata-extraction.md)
- [Document Pipeline](docs/features/document-pipeline.md)
- [Agentic Retrieval & Chat](docs/features/agentic-retrieval.md)
- [Chat UI](docs/features/chat.md)

## References

- [docs/SECURITY.md](docs/SECURITY.md) — security principles and implementation
- [docs/RELIABILITY.md](docs/RELIABILITY.md) — reliability expectations
- [AGENTS.md](AGENTS.md) — architectural invariants and agent instructions
