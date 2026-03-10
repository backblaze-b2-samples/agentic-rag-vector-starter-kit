<!-- last_verified: 2026-03-10 -->
# Agentic RAG Vector Starter Kit Transformation

## Goal

Transform the existing file management starter kit into a production-ready Agentic RAG system with:
- LanceDB as vector store (backed by B2 bucket storage)
- LangChain for orchestration (document processing + retrieval chains)
- Document ingestion pipeline (metadata, classification, chunking, summarization, embeddings)
- ChatGPT/Claude-style chat UI with source citations
- Best-practice agentic retrieval flow (9-step pipeline)

## Architecture Overview

```
User uploads doc → Pipeline: extract → classify → chunk → summarize → embed → store in LanceDB (on B2)
User asks question → Agent: intent → query plan → retrieve → fuse → rerank → validate → generate → cite
```

### New Backend Layers (within existing architecture)

```
types/
  chat.py          - ChatMessage, ConversationState, Citation, AgentResponse
  documents.py     - DocumentChunk, ProcessedDocument, ClassificationResult
  retrieval.py     - QueryPlan, CandidateResult, EvidenceSet, RetrievalMetrics

config/
  settings.py      - Add LLM, embedding model, LanceDB, chunking settings

repo/
  b2_client.py     - (existing) file storage
  lancedb_client.py - LanceDB connection, table ops, vector search
  llm_client.py    - LangChain LLM wrapper (embeddings, chat, reranking)

service/
  upload.py         - (existing) extend to trigger pipeline
  pipeline.py       - Document processing orchestrator
  chunker.py        - Text splitting strategies
  classifier.py     - Document type classification
  summarizer.py     - Per-chunk and whole-doc summaries
  embedder.py       - Embedding generation via LangChain
  retrieval.py      - Agentic RAG retrieval engine (9-step flow)
  chat.py           - Conversation management, context construction

runtime/
  upload.py         - (existing) extend with processing status
  chat.py           - Chat endpoints (send message, get history, stream)
  documents.py      - Document status, chunks, search endpoints
```

### New Frontend Pages

```
apps/web/src/
  app/chat/page.tsx          - Chat interface
  components/chat/
    chat-container.tsx        - Main chat layout
    message-list.tsx          - Message display with streaming
    message-bubble.tsx        - Individual message with citations
    citation-panel.tsx        - Side panel showing source documents
    chat-input.tsx            - Input with file attachment option
  components/documents/
    processing-status.tsx     - Pipeline progress indicator
    document-chunks.tsx       - View chunks for a document
```

### LanceDB Storage on B2

LanceDB supports S3-compatible storage. Tables stored at:
`s3://{bucket}/lancedb/` using the same B2 credentials.

Tables:
- `document_chunks` - chunk text, embeddings, metadata (doc_id, chunk_id, title, section_path, source, updated_at, classification, sensitivity)
- `conversations` - chat history with references

---

## Phases

### Phase 1: Foundation & Dependencies
**Files to create/modify:**
- `services/api/requirements.txt` — add lancedb, langchain, langchain-anthropic, langchain-community, tiktoken
- `services/api/app/config/settings.py` — add LLM/embedding/LanceDB/chunking config
- `services/api/app/types/chat.py` — chat and agent response models
- `services/api/app/types/documents.py` — document processing models
- `services/api/app/types/retrieval.py` — retrieval pipeline models
- `services/api/app/repo/lancedb_client.py` — LanceDB connection, CRUD, vector search
- `services/api/app/repo/llm_client.py` — LangChain LLM/embedding wrapper
- `.env.example` — add ANTHROPIC_API_KEY, EMBEDDING_MODEL, LANCEDB_URI settings
- `packages/shared/src/types.ts` — add TypeScript mirrors of new models
- Tests for repo layer

### Phase 2: Document Processing Pipeline
**Files to create/modify:**
- `services/api/app/service/chunker.py` — recursive text splitting (by doc type)
- `services/api/app/service/classifier.py` — LLM-based doc classification
- `services/api/app/service/summarizer.py` — chunk + document summarization
- `services/api/app/service/embedder.py` — batch embedding generation
- `services/api/app/service/pipeline.py` — orchestrator (extract → classify → chunk → summarize → embed → store)
- `services/api/app/service/upload.py` — extend to trigger pipeline after B2 upload
- `services/api/app/runtime/documents.py` — endpoints: processing status, list chunks, search
- `services/api/app/types/documents.py` — refine as needed
- `docs/features/document-pipeline.md` — feature doc
- Tests for each service module

### Phase 3: Agentic Retrieval Engine
**Files to create/modify:**
- `services/api/app/service/retrieval.py` — full 9-step agentic retrieval:
  1. Parse inputs/constraints (ACL, tenant, permissions)
  2. Intent classification and routing (kb_only | no_retrieval | etc.)
  3. Query planning (2-5 variants: keyword, semantic, identifier-focused)
  4. Candidate retrieval (parallel vector + optional lexical)
  5. Fusion and deduplication (RRF scoring, ACL filtering)
  6. Reranking (LLM-based relevance judge, top 5-12)
  7. Evidence validation + gap handling (1-2 retry loops)
  8. Context construction (compact evidence pack with citations)
  9. Post-retrieval logging (query plan, evidence IDs, metrics)
- `services/api/app/service/chat.py` — conversation state, context management
- `services/api/app/runtime/chat.py` — endpoints: POST /chat, GET /chat/history, SSE streaming
- `services/api/app/types/retrieval.py` — refine as needed
- `docs/features/agentic-retrieval.md` — feature doc
- Tests for retrieval pipeline

### Phase 4: Chat UI
**Files to create/modify:**
- `apps/web/src/app/chat/page.tsx` — chat page
- `apps/web/src/components/chat/chat-container.tsx` — layout (messages + citation panel)
- `apps/web/src/components/chat/message-list.tsx` — scrollable message list
- `apps/web/src/components/chat/message-bubble.tsx` — message with inline citation links
- `apps/web/src/components/chat/citation-panel.tsx` — expandable source panel
- `apps/web/src/components/chat/chat-input.tsx` — input bar with send button
- `apps/web/src/lib/api-client.ts` — add chat API methods + SSE support
- `packages/shared/src/types.ts` — add chat-related types
- `apps/web/src/app/layout.tsx` — add Chat nav link
- `docs/features/chat.md` — feature doc

### Phase 5: Integration & Polish
**Files to modify:**
- Upload flow: show processing status after upload completes
- Dashboard: add RAG stats (total chunks, avg retrieval latency, conversations count)
- File browser: show chunk count per document, link to chat with doc context
- Navigation: update for new pages
- `ARCHITECTURE.md` — update with new components, data flows, LanceDB
- `AGENTS.md` — update repository map, invariants (lancedb only in repo/, langchain LLM calls only in repo/)
- `README.md` — update project description, setup, features
- `.env.example` — finalize all new env vars
- End-to-end tests
- `docs/app-workflows.md` — update with chat and pipeline workflows

---

## Key Design Decisions

1. **LanceDB on B2**: Use S3-compatible storage URI so vector data lives alongside documents in B2. No separate vector DB infrastructure.

2. **LangChain scope**: Use for document loaders, text splitters, embedding models, and LLM calls. Don't use LangChain's agent framework — build the agentic loop explicitly for transparency and control.

3. **Embedding model**: Default to a local/API embedding model via LangChain (configurable). Support Anthropic for chat + classification, OpenAI or open-source for embeddings.

4. **Streaming**: Use Server-Sent Events (SSE) for chat responses. FastAPI `StreamingResponse` → frontend `EventSource`.

5. **No separate DB**: Continue the "no database" philosophy. LanceDB tables on B2 store vector data. Conversation history stored in LanceDB or B2 JSON files.

6. **Repo layer isolation**: `lancedb` SDK confined to `repo/lancedb_client.py`. `langchain` LLM/embedding calls confined to `repo/llm_client.py`. Service layer uses abstract interfaces.

7. **Processing is async-like**: After upload, pipeline runs synchronously for MVP (document processing is fast enough for typical docs). Can add background task queue later.

8. **Citation format**: Each response chunk includes `[1]`, `[2]` etc. linked to source documents with title, section, page number, and presigned download URL.

---

## New Environment Variables

```
# LLM (Anthropic for chat/classification)
ANTHROPIC_API_KEY=your_key
LLM_MODEL=claude-sonnet-4-20250514

# Embeddings
EMBEDDING_PROVIDER=openai          # or "huggingface" for local
EMBEDDING_MODEL=text-embedding-3-small
OPENAI_API_KEY=your_key            # if using OpenAI embeddings

# LanceDB
LANCEDB_URI=s3://{bucket}/lancedb/?region=us-west-004&endpoint=https://s3.us-west-004.backblazeb2.com

# Pipeline
CHUNK_SIZE=1000
CHUNK_OVERLAP=200
MAX_CHUNKS_PER_DOC=500
```

---

## Validation Criteria

- [ ] Documents uploaded via existing flow get automatically processed (chunked, embedded, stored)
- [ ] Chat UI renders with streaming responses
- [ ] Responses include clickable citations linking to source documents
- [ ] Vector search returns relevant chunks for queries
- [ ] Agentic retrieval loop retries on insufficient evidence
- [ ] All existing tests still pass
- [ ] New structural tests enforce lancedb/langchain SDK isolation in repo/
- [ ] `pnpm lint && pnpm lint:api && pnpm test:api && pnpm check:structure` passes
- [ ] Docs updated for all new features
