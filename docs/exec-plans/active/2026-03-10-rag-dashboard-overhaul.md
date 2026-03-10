# RAG Dashboard Overhaul + Upload UX + B2 Health

## Goals
1. B2 credential check on startup with logging
2. Upload shows chunks/summaries live as pipeline runs
3. Dashboard redesigned around RAG operations (not file management)

## Data Sources (already captured)
- `RetrievalMetrics`: route, queries_generated, total_candidates, evidence_count, retrieval_loops, latency_ms
- `RankedEvidence`: relevance_score per evidence chunk, doc_id, doc_title
- `ProcessedDocument`: chunk_count, total_tokens, classification, status, error_message
- `EvidenceSet`: is_sufficient, gap_description
- LanceDB: total chunks, per-doc chunk counts

## Excluded (not supported by current data)
- User ratings/notes
- Cost tracking (no pricing data)
- Cache hit rates
- Token in/out per query (LangChain doesn't expose this without callbacks)

## Phase 1: Backend - Query Log + B2 Check

### 1a. SQLite query log (`repo/query_log.py`)
Log one JSON record per query with fields from RetrievalMetrics + top scores:
- ts, query, route, queries_generated, total_candidates, evidence_count
- retrieval_loops, latency_ms, top1_score, top5_scores
- chunks_returned, chunks_used, is_sufficient
Store in `data/query_log.sqlite` (auto-created)

### 1b. SQLite ingestion log (`repo/query_log.py`)
Log per-ingestion: ts, doc_id, filename, status, chunk_count, total_tokens, classification, error_message

### 1c. Dashboard API endpoints (`runtime/dashboard.py`)
- GET /dashboard/stats - corpus size, query counts, avg scores, p95 latency
- GET /dashboard/queries?limit=20 - recent queries with scores
- GET /dashboard/ingestions?limit=20 - recent ingestions
- GET /dashboard/retrieval-quality - % below threshold, avg top-1, retry stats

### 1d. B2 startup check (`main.py`)
On app startup, check B2 connectivity and log result.

### 1e. Health endpoint enhancement
Add LanceDB connectivity check alongside B2.

## Phase 2: Upload UX - Pipeline SSE Stream

### 2a. Pipeline SSE endpoint (`runtime/upload.py`)
POST /upload returns the result, but also add a new endpoint or modify the upload response to include pipeline results (chunks, summaries, classification).

Simpler approach: return ProcessedDocument details in the upload response (already partially there). Enhance the response to include chunk details.

### 2b. Frontend upload processing detail
Replace the simple spinner with a detailed card showing:
- Classification result
- Chunk count + avg chunk size
- Document summary
- List of chunk summaries (collapsible)

## Phase 3: Frontend Dashboard Redesign

### 3a. Quick Status cards
- Queries today / last 7 days
- Last ingestion timestamp
- Corpus: docs + chunks
- p95 latency (last 50)

### 3b. Retrieval Quality panel
- Avg top-1 score (7 days)
- % queries below 0.3 threshold
- Recent queries table with scores, latency, evidence count

### 3c. Ingestion panel
- Recent ingestions with status, chunks, classification
- Failed ingestion count + last error

### 3d. Agent Behavior panel
- Retrieval invoked rate
- Retry loop rate
- Avg score improvement on retry

## File Changes
- NEW: `services/api/app/repo/query_log.py` (SQLite ops)
- NEW: `services/api/app/service/dashboard.py` (aggregation logic)
- NEW: `services/api/app/runtime/dashboard.py` (API endpoints)
- EDIT: `services/api/app/service/chat.py` (log queries after retrieval)
- EDIT: `services/api/app/service/pipeline.py` (log ingestions)
- EDIT: `services/api/app/runtime/health.py` (add LanceDB check)
- EDIT: `services/api/main.py` (startup B2 check, register dashboard router)
- EDIT: `services/api/app/repo/__init__.py` (export query_log functions)
- NEW: `apps/web/src/components/dashboard/quick-status.tsx`
- NEW: `apps/web/src/components/dashboard/retrieval-quality.tsx`
- NEW: `apps/web/src/components/dashboard/ingestion-panel.tsx`
- NEW: `apps/web/src/components/dashboard/agent-behavior.tsx`
- NEW: `apps/web/src/components/dashboard/recent-queries-table.tsx`
- EDIT: `apps/web/src/app/page.tsx` (new dashboard layout)
- EDIT: `apps/web/src/components/upload/processing-status.tsx` (show pipeline detail)
- EDIT: `apps/web/src/lib/api-client.ts` (dashboard API functions)
