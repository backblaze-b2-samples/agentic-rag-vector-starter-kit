"""Chat service — conversation management and grounded answer generation."""

import json
import logging
import threading
from datetime import UTC, datetime

from app.repo import (
    chat_completion,
    chat_completion_stream,
    get_presigned_url,
    log_query,
    update_eval_scores,
)
from app.service.retrieval import retrieve, retrieve_with_steps
from app.service.sessions import generate_title, new_session, store_message
from app.types import (
    ChatMessage,
    ChatRequest,
    ChatResponse,
    Citation,
    MessageRole,
    RetrievalInfo,
)

logger = logging.getLogger(__name__)

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


def _resolve_session_id(request: ChatRequest) -> tuple[str, bool]:
    """Resolve session_id from request. Returns (session_id, is_new)."""
    sid = request.session_id or request.conversation_id
    if sid:
        return sid, False
    session = new_session()
    return session.session_id, True


def _log_query_metrics(query: str, evidence_set, metrics, session_id: str | None = None) -> str:
    """Log query metrics to SQLite for dashboard. Returns timestamp for eval linkage."""
    ts = datetime.now(UTC).isoformat()
    try:
        scores = [ev.relevance_score for ev in evidence_set.evidence if ev.relevance_score is not None]
        log_query(
            query=query, route=metrics.route,
            queries_generated=metrics.queries_generated,
            total_candidates=metrics.total_candidates,
            post_fusion_candidates=metrics.post_fusion_candidates,
            post_rerank_count=metrics.post_rerank_count,
            evidence_count=metrics.evidence_count,
            retrieval_loops=metrics.retrieval_loops,
            latency_ms=metrics.latency_ms,
            top1_score=scores[0] if scores else None,
            top5_scores=scores[:5],
            is_sufficient=evidence_set.is_sufficient,
            session_id=session_id,
        )
    except Exception:
        logger.warning("Failed to log query metrics", exc_info=True)
    return ts


def _run_eval_async(query_ts: str, answer: str, question: str, evidence_set) -> None:
    """Run RAGAS evaluation in a background thread (non-blocking)."""
    def _eval():
        try:
            from app.service.eval_metrics import score_context_precision, score_faithfulness
            evidence_texts = [ev.text for ev in evidence_set.evidence]
            faith = score_faithfulness(answer, evidence_texts)
            ctx_prec = score_context_precision(question, evidence_texts)
            update_eval_scores(query_ts, faith, ctx_prec)
            logger.info("[eval] RAGAS scores: faithfulness=%.2f context_precision=%.2f",
                        faith or 0, ctx_prec or 0)
        except Exception:
            logger.warning("RAGAS evaluation failed", exc_info=True)
    threading.Thread(target=_eval, daemon=True).start()


def _build_citations(evidence_set) -> list[Citation]:
    """Convert ranked evidence into citation objects with download URLs."""
    citations = []
    for i, ev in enumerate(evidence_set.evidence):
        download_url = None
        try:
            download_url = get_presigned_url(ev.doc_id, filename=ev.source_filename)
        except Exception:
            logger.warning("Failed to generate download URL for %s", ev.doc_id)
        citations.append(Citation(
            index=i + 1, doc_id=ev.doc_id, doc_title=ev.doc_title,
            section_path=ev.section_path, source_filename=ev.source_filename,
            page=ev.page if ev.page and ev.page > 0 else None,
            chunk_text=ev.text[:500], download_url=download_url,
        ))
    return citations


def _build_evidence_block(evidence_set) -> str:
    """Format evidence chunks for the LLM context window."""
    if not evidence_set.evidence:
        return "No relevant evidence found."
    blocks = []
    for i, ev in enumerate(evidence_set.evidence):
        blocks.append(f"[{i + 1}] Source: {ev.doc_title} > {ev.section_path}\n{ev.text}")
    return "\n\n---\n\n".join(blocks)


def _build_history_context(session_id: str) -> str:
    """Build conversation context from recent session messages."""
    from app.repo.session_store import get_messages
    messages = get_messages(session_id)
    if len(messages) <= 1:
        return ""
    recent = messages[-6:]
    return "\nConversation context:\n" + "\n".join(
        f"{m['role']}: {m['content'][:300]}" for m in recent
    ) + "\n"


def handle_chat(request: ChatRequest) -> ChatResponse:
    """Process a chat message through the agentic retrieval pipeline."""
    session_id, is_new = _resolve_session_id(request)

    # Persist user message
    store_message(session_id, "user", request.message)

    # Auto-title on first message
    if is_new:
        generate_title(session_id, request.message)

    # Run retrieval
    evidence_set, metrics = retrieve(request.message)
    query_ts = _log_query_metrics(request.message, evidence_set, metrics, session_id)

    # Generate answer
    if metrics.route == "no_retrieval":
        answer_text = chat_completion(
            system_prompt=_CONVERSATIONAL_PROMPT,
            user_message=request.message, temperature=0.3,
        )
        citations = []
    else:
        evidence_block = _build_evidence_block(evidence_set)
        system_prompt = _ANSWER_SYSTEM_PROMPT.format(evidence=evidence_block)
        context = _build_history_context(session_id)
        answer_text = chat_completion(
            system_prompt=system_prompt,
            user_message=f"{context}Question: {request.message}",
            temperature=0.3,
        )
        citations = _build_citations(evidence_set)

    retrieval_info = RetrievalInfo(
        route=metrics.route, queries_generated=metrics.queries_generated,
        candidates_found=metrics.total_candidates,
        evidence_used=metrics.evidence_count,
        retrieval_loops=metrics.retrieval_loops, latency_ms=metrics.latency_ms,
    )

    # Persist assistant message
    store_message(
        session_id, "assistant", answer_text,
        citations=[c.model_dump() for c in citations],
        retrieval_metadata=retrieval_info.model_dump(),
    )

    # Background RAGAS evaluation (non-blocking)
    if metrics.route != "no_retrieval" and evidence_set.evidence:
        _run_eval_async(query_ts, answer_text, request.message, evidence_set)

    assistant_msg = ChatMessage(
        role=MessageRole.assistant, content=answer_text, citations=citations,
    )
    return ChatResponse(
        conversation_id=session_id, message=assistant_msg,
        retrieval_metadata=retrieval_info,
    )


def handle_chat_stream(request: ChatRequest):
    """Stream a chat response via SSE. Yields SSE-formatted strings."""
    session_id, is_new = _resolve_session_id(request)
    store_message(session_id, "user", request.message)

    if is_new:
        generate_title(session_id, request.message)

    # Run retrieval with live step streaming
    evidence_set = None
    metrics = None
    for item in retrieve_with_steps(request.message):
        if item[0] == "step":
            yield f"data: {json.dumps({'type': 'step', 'label': item[1], 'status': item[2]})}\n\n"
        elif item[0] == "result":
            evidence_set, metrics = item[1], item[2]

    query_ts = _log_query_metrics(request.message, evidence_set, metrics, session_id)

    retrieval_info = RetrievalInfo(
        route=metrics.route, queries_generated=metrics.queries_generated,
        candidates_found=metrics.total_candidates,
        evidence_used=metrics.evidence_count,
        retrieval_loops=metrics.retrieval_loops, latency_ms=metrics.latency_ms,
    )

    # Metadata event (includes session_id for frontend)
    yield f"data: {json.dumps({'type': 'metadata', 'conversation_id': session_id, 'session_id': session_id, 'retrieval': retrieval_info.model_dump()})}\n\n"

    # Citations event
    if metrics.route != "no_retrieval":
        citations = _build_citations(evidence_set)
        yield f"data: {json.dumps({'type': 'citations', 'citations': [c.model_dump() for c in citations]})}\n\n"
    else:
        citations = []

    # Build prompt
    context = _build_history_context(session_id)
    if metrics.route == "no_retrieval":
        system_prompt = _CONVERSATIONAL_PROMPT
        user_message = request.message
    else:
        evidence_block = _build_evidence_block(evidence_set)
        system_prompt = _ANSWER_SYSTEM_PROMPT.format(evidence=evidence_block)
        user_message = f"{context}Question: {request.message}"

    # Emit "generating answer" step
    yield f"data: {json.dumps({'type': 'step', 'label': 'Generating answer...', 'status': 'active'})}\n\n"

    # Stream answer tokens
    full_response = ""
    for token in chat_completion_stream(system_prompt=system_prompt, user_message=user_message):
        full_response += token
        yield f"data: {json.dumps({'type': 'token', 'content': token})}\n\n"

    yield f"data: {json.dumps({'type': 'step', 'label': 'Generating answer...', 'status': 'done'})}\n\n"
    yield f"data: {json.dumps({'type': 'done'})}\n\n"

    # Persist assistant message
    store_message(
        session_id, "assistant", full_response,
        citations=[c.model_dump() for c in citations],
        retrieval_metadata=retrieval_info.model_dump(),
    )

    # Background RAGAS evaluation (non-blocking)
    if metrics.route != "no_retrieval" and evidence_set.evidence:
        _run_eval_async(query_ts, full_response, request.message, evidence_set)
