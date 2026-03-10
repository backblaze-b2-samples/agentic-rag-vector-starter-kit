<!-- last_verified: 2026-03-10 -->
# Agentic Retrieval & Chat

## Purpose

9-step agentic RAG pipeline that retrieves evidence from the vector store and generates grounded, cited answers.

## Retrieval Pipeline (service/retrieval.py + service/reranker.py)

```
User question
  → Step 1: Parse inputs/constraints
  → Step 2: Intent classification (kb_only | no_retrieval)
  → Step 3: Query planning (2-5 variants: semantic, keyword, identifier)
  → Step 4: Candidate retrieval (vector search per variant, k=30 each)
  → Step 5: Fusion + dedup (RRF scoring, top 40)
  → Step 6: Reranking (LLM relevance judge, top 12) — reranker.py
  → Step 7: Evidence validation + gap handling (max 2 loops) — reranker.py
  → Step 8: Context construction (in chat.py)
  → Step 9: Metrics logging
```

### Intent Routing

- `no_retrieval` — conversational messages (greetings, thanks), answered directly
- `kb_only` — questions needing document evidence

### Query Planning

LLM generates 2-5 query variants per question:
- Semantic: natural language paraphrases
- Keyword: key terms, acronyms, proper nouns
- Identifier: error codes, IDs (when detected)

Original question always included as a variant.

### Retrieval + Fusion

- Vector search via LanceDB for each query variant
- Reciprocal Rank Fusion (RRF) merges results across variants
- Chunks appearing in multiple variant results get boosted scores
- Deduplication by chunk_id

### Reranking

- LLM scores each candidate 0.0-1.0 against the question
- Chunks below 0.3 confidence threshold filtered out
- Top 12 retained for answer generation

### Gap Handling

- LLM assesses if evidence is sufficient
- If not, identifies missing information
- Query refined with gap description, retrieval retried (max 2 loops)
- Stops on: sufficient evidence, no new high-quality evidence, or loop limit

## Chat Service (service/chat.py)

- Conversation state management (in-memory, keyed by conversation_id)
- Grounded answer generation with citation insertion ([1], [2], etc.)
- Citation objects include: doc title, section, page, text excerpt, presigned download URL
- Conversation context: last 5 messages included for follow-up questions
- SSE streaming: metadata → citations → tokens → done

## API Endpoints

| Method | Endpoint | Purpose |
|--------|----------|---------|
| POST | `/chat` | Send message, get grounded response with citations |
| POST | `/chat/stream` | SSE streaming response |
| GET | `/chat/history/{conversation_id}` | Get conversation history |

### SSE Event Format

```
data: {"type": "metadata", "conversation_id": "...", "retrieval": {...}}
data: {"type": "citations", "citations": [...]}
data: {"type": "token", "content": "..."}
data: {"type": "done"}
data: {"type": "error", "detail": "..."}  // on failure
```

### ChatResponse Schema

```json
{
  "conversation_id": "uuid",
  "message": {
    "role": "assistant",
    "content": "Answer text with [1] citations...",
    "citations": [
      {
        "index": 1,
        "doc_id": "uploads/doc.pdf",
        "doc_title": "Guide",
        "section_path": "Setup > Prerequisites",
        "source_filename": "doc.pdf",
        "page": 3,
        "chunk_text": "Relevant excerpt...",
        "download_url": "https://..."
      }
    ]
  },
  "retrieval_metadata": {
    "route": "kb_only",
    "queries_generated": 3,
    "candidates_found": 45,
    "evidence_used": 5,
    "retrieval_loops": 1,
    "latency_ms": 1200.0
  }
}
```

## Tests

- `tests/test_retrieval.py` — intent classification, query planning, RRF fusion, evidence validation
- `tests/test_chat.py` — chat handling, citations, conversation history
