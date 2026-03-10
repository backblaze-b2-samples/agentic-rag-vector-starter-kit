"""Chat service — conversation management and grounded answer generation."""

import json
import logging
import uuid
from datetime import UTC, datetime

from app.repo import chat_completion, chat_completion_stream, get_presigned_url
from app.service.retrieval import retrieve
from app.types import (
    ChatMessage,
    ChatRequest,
    ChatResponse,
    Citation,
    MessageRole,
    RetrievalInfo,
)

logger = logging.getLogger(__name__)

# In-memory conversation store (swap for LanceDB/B2 persistence later)
_conversations: dict[str, list[ChatMessage]] = {}


def clear_conversations() -> None:
    """Clear all conversations. Used by tests to prevent cross-contamination."""
    _conversations.clear()

_ANSWER_SYSTEM_PROMPT = """You are a helpful assistant that answers questions using the provided evidence.

Rules:
- Use ONLY the provided evidence for factual claims
- Cite sources using [1], [2], etc. matching the evidence indices
- If evidence is insufficient, say what's missing and what was searched
- Structure your answer clearly: summary first, then details
- Be concise and direct

Evidence:
{evidence}"""

_CONVERSATIONAL_PROMPT = """You are a helpful assistant for a document knowledge base.
Respond naturally to conversational messages. Be concise and friendly.
If the user seems to be asking about documents, suggest they ask a specific question."""


def _build_citations(evidence_set) -> list[Citation]:
    """Convert ranked evidence into citation objects with download URLs."""
    citations = []
    for i, ev in enumerate(evidence_set.evidence):
        # Generate presigned URL for the source document
        download_url = None
        try:
            download_url = get_presigned_url(ev.doc_id, filename=ev.source_filename)
        except Exception:
            logger.warning("Failed to generate download URL for %s", ev.doc_id)

        citations.append(Citation(
            index=i + 1,
            doc_id=ev.doc_id,
            doc_title=ev.doc_title,
            section_path=ev.section_path,
            source_filename=ev.source_filename,
            page=ev.page if ev.page and ev.page > 0 else None,
            chunk_text=ev.text[:500],
            download_url=download_url,
        ))
    return citations


def _build_evidence_block(evidence_set) -> str:
    """Format evidence chunks for the LLM context window."""
    if not evidence_set.evidence:
        return "No relevant evidence found."

    blocks = []
    for i, ev in enumerate(evidence_set.evidence):
        blocks.append(
            f"[{i + 1}] Source: {ev.doc_title} > {ev.section_path}\n{ev.text}"
        )
    return "\n\n---\n\n".join(blocks)


def get_conversation(conversation_id: str) -> list[ChatMessage]:
    """Get conversation history."""
    return _conversations.get(conversation_id, [])


def handle_chat(request: ChatRequest) -> ChatResponse:
    """Process a chat message through the agentic retrieval pipeline.

    Steps:
    1. Get or create conversation
    2. Run retrieval pipeline
    3. Build grounded answer with citations
    4. Store in conversation history
    """
    # Get or create conversation
    conv_id = request.conversation_id or str(uuid.uuid4())
    history = _conversations.setdefault(conv_id, [])

    # Store user message
    user_msg = ChatMessage(
        role=MessageRole.user,
        content=request.message,
        timestamp=datetime.now(UTC),
    )
    history.append(user_msg)

    # Run retrieval (Step 8: context construction happens here)
    evidence_set, metrics = retrieve(request.message)

    # Generate grounded answer
    if metrics.route == "no_retrieval":
        # Conversational response — no evidence needed
        answer_text = chat_completion(
            system_prompt=_CONVERSATIONAL_PROMPT,
            user_message=request.message,
            temperature=0.3,
        )
        citations = []
    else:
        # Build evidence context and generate answer
        evidence_block = _build_evidence_block(evidence_set)
        system_prompt = _ANSWER_SYSTEM_PROMPT.format(evidence=evidence_block)

        # Include recent conversation context
        recent_context = ""
        if len(history) > 1:
            recent_msgs = history[-6:-1]  # last 5 messages before current
            recent_context = "\n".join(
                f"{m.role.value}: {m.content}" for m in recent_msgs
            )
            recent_context = f"\nConversation context:\n{recent_context}\n"

        answer_text = chat_completion(
            system_prompt=system_prompt,
            user_message=f"{recent_context}Question: {request.message}",
            temperature=0.3,
        )
        citations = _build_citations(evidence_set)

    # Build assistant message
    assistant_msg = ChatMessage(
        role=MessageRole.assistant,
        content=answer_text,
        citations=citations,
        timestamp=datetime.now(UTC),
    )
    history.append(assistant_msg)

    return ChatResponse(
        conversation_id=conv_id,
        message=assistant_msg,
        retrieval_metadata=RetrievalInfo(
            route=metrics.route,
            queries_generated=metrics.queries_generated,
            candidates_found=metrics.total_candidates,
            evidence_used=metrics.evidence_count,
            retrieval_loops=metrics.retrieval_loops,
            latency_ms=metrics.latency_ms,
        ),
    )


def handle_chat_stream(request: ChatRequest):
    """Stream a chat response via SSE.

    Yields SSE-formatted strings: "data: {json}\n\n"
    First yields citations, then streams answer tokens.
    """
    conv_id = request.conversation_id or str(uuid.uuid4())
    history = _conversations.setdefault(conv_id, [])

    user_msg = ChatMessage(
        role=MessageRole.user,
        content=request.message,
        timestamp=datetime.now(UTC),
    )
    history.append(user_msg)

    # Run retrieval
    evidence_set, metrics = retrieve(request.message)

    # Send metadata event
    retrieval_info = RetrievalInfo(
        route=metrics.route,
        queries_generated=metrics.queries_generated,
        candidates_found=metrics.total_candidates,
        evidence_used=metrics.evidence_count,
        retrieval_loops=metrics.retrieval_loops,
        latency_ms=metrics.latency_ms,
    )
    yield f"data: {json.dumps({'type': 'metadata', 'conversation_id': conv_id, 'retrieval': retrieval_info.model_dump()})}\n\n"

    # Send citations event
    if metrics.route != "no_retrieval":
        citations = _build_citations(evidence_set)
        citations_data = [c.model_dump() for c in citations]
        yield f"data: {json.dumps({'type': 'citations', 'citations': citations_data})}\n\n"
    else:
        citations = []

    # Build conversation context for multi-turn support
    recent_context = ""
    if len(history) > 1:
        recent_msgs = history[-6:-1]
        recent_context = "\n".join(
            f"{m.role.value}: {m.content}" for m in recent_msgs
        )
        recent_context = f"\nConversation context:\n{recent_context}\n"

    # Stream answer tokens
    if metrics.route == "no_retrieval":
        system_prompt = _CONVERSATIONAL_PROMPT
        user_message = request.message
    else:
        evidence_block = _build_evidence_block(evidence_set)
        system_prompt = _ANSWER_SYSTEM_PROMPT.format(evidence=evidence_block)
        user_message = f"{recent_context}Question: {request.message}"

    full_response = ""
    for token in chat_completion_stream(
        system_prompt=system_prompt,
        user_message=user_message,
    ):
        full_response += token
        yield f"data: {json.dumps({'type': 'token', 'content': token})}\n\n"

    # Send done event
    yield f"data: {json.dumps({'type': 'done'})}\n\n"

    # Store assistant message in history
    assistant_msg = ChatMessage(
        role=MessageRole.assistant,
        content=full_response,
        citations=citations,
        timestamp=datetime.now(UTC),
    )
    history.append(assistant_msg)
