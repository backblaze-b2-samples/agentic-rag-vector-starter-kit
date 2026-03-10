<!-- last_verified: 2026-03-10 -->
# Chat UI

## Purpose

ChatGPT/Claude-style conversational interface for querying documents with grounded, cited responses.

## Frontend Components

```
apps/web/src/
  app/chat/page.tsx                    — Chat page (full height)
  components/chat/
    chat-container.tsx                  — Main orchestrator (messages, streaming, citations)
    chat-input.tsx                      — Textarea with auto-resize, Enter to send
    message-bubble.tsx                  — User/assistant bubbles with inline [N] citation links
    citation-panel.tsx                  — Side panel listing all sources with excerpts + download links
```

## User Flow

1. User navigates to `/chat` via sidebar
2. Empty state shows "Ask your documents" prompt
3. User types question, presses Enter or clicks Send
4. Streaming begins:
   - "Searching documents..." indicator while retrieval runs
   - Tokens stream in as the LLM generates the answer
   - Citation panel slides open if sources were used
5. User clicks `[1]`, `[2]` etc. in the response → citation highlighted in panel
6. Panel shows: doc title, section path, page number, text excerpt, "View source" download link

## Streaming Protocol (SSE)

Frontend connects via `POST /chat/stream`. Events arrive in order:

1. `metadata` — conversation_id, retrieval metrics
2. `citations` — array of Citation objects
3. `token` (repeated) — text chunks as they arrive
4. `done` — signals stream complete
5. `error` — emitted on failure (detail field describes the issue)

## Key Behaviors

- **Auto-scroll**: Messages area scrolls to bottom on new content
- **Multi-turn**: Conversation ID maintained for follow-up questions
- **Abort**: AbortController cancels in-flight requests if user navigates away
- **Error handling**: Toast notification on failure, empty assistant messages removed
- **Retrieval badges**: Shows "N sources used", "N queries", "Nms" after each response
- **Keyboard**: Enter sends, Shift+Enter for newlines

## API Integration

- `streamChatMessage()` — SSE streaming via fetch ReadableStream (used by chat UI)
- `sendChatMessage()` — non-streaming POST /chat (exported for programmatic use)
- `getChatHistory()` — retrieve past conversation
- `searchDocuments()` — direct semantic search
- `getDocumentStats()` — vector store stats

## Navigation

Chat is the second item in the sidebar (after Dashboard), using the `MessageSquare` lucide icon.
