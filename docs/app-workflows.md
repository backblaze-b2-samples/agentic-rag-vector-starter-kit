<!-- last_verified: 2026-03-10 -->
# App Workflows

User journeys inside the application.

## Chat with Documents

- User navigates to `/chat`
- Empty state shows "Ask your documents" prompt
- User types a question and presses Enter (or clicks Send)
- System runs agentic retrieval: intent classification → query planning → vector search → reranking → evidence validation
- Answer streams in token-by-token via SSE
- Inline `[1]`, `[2]` citation links in the response are clickable
- Citation panel slides open showing: doc title, section, page, excerpt, download link
- Retrieval badges show: sources used, queries generated, latency
- Multi-turn: follow-up questions use the same conversation context
- Conversational messages (greetings, thanks) are answered directly without retrieval
- See: [Agentic Retrieval & Chat](features/agentic-retrieval.md), [Chat UI](features/chat.md)

## Upload Files

- User navigates to `/upload`
- Drops or selects files in the dropzone
- Client validates file size (max 100MB) and type
- Progress bar shows per-file upload status
- On success: toast notification, green checkmark
- RAG processing status appears: "Processing — chunking, classifying, embedding..."
- Text documents (PDF, TXT, CSV, Markdown, JSON) are automatically chunked, classified, summarized, and embedded into the vector store
- Non-text files (images, audio, video) are uploaded to B2 but skip RAG processing
- On failure: red status icon with error message
- User can clear completed uploads
- See: [File Upload](features/file-upload.md), [Document Pipeline](features/document-pipeline.md)

## Browse and Manage Files

- User navigates to `/files`
- Page loads file list from API (sorted most recent first)
- Files displayed in tree view with folders and type-specific icons
- Top-level folders auto-expand on load
- Hover a file row to see action buttons (preview / download / delete)
- **Preview**: opens dialog with image/PDF preview + metadata panel
- **Download**: fetches presigned URL, browser downloads file
- **Delete**: removes file from B2, row removed from tree, toast confirms
- Empty bucket shows "No files found" with upload prompt
- See: [File Browser](features/file-browser.md)

## View Dashboard

- User navigates to `/` (home)
- Three parallel API calls load: stats, recent files, upload activity
- Stats cards show: total files, storage used, uploads today, total downloads
- Upload chart shows last 7 days of upload activity as bar chart
- Recent uploads table shows last 10 files with filename, size, type, date
- Empty state: "No files uploaded yet" messages
- See: [Dashboard](features/dashboard.md)
