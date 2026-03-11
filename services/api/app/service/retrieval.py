"""Agentic retrieval engine — multi-step pipeline from query to evidence.

Intent → query rewrite → plan → retrieve (hybrid/vector) → fuse → rerank
(cross-encoder) → CRAG correction → validate → metrics.
"""

import json
import logging
import re
import time
from collections.abc import Generator

from app.repo import (
    chat_completion,
    generate_query_embedding,
    get_corpus_index,
    search_hybrid,
    search_vectors,
)
from app.service._retrieval_prompts import INTENT_PROMPT, QUERY_PLAN_PROMPT, REWRITE_PROMPT
from app.service.crag import assess_and_correct
from app.service.reranker import rerank_candidates, validate_evidence
from app.types import (
    CandidateChunk,
    EvidenceSet,
    IntentClassification,
    QueryPlan,
    QueryVariant,
    RetrievalMetrics,
    RetrievalRoute,
)

logger = logging.getLogger(__name__)

MAX_RETRIEVAL_LOOPS = 2
CANDIDATE_K = 30


def _extract_json(text: str) -> dict:
    """Parse JSON from LLM output, stripping markdown code fences if present."""
    cleaned = text.strip()
    cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
    cleaned = re.sub(r"\s*```$", "", cleaned)
    return json.loads(cleaned.strip())


def _step2b_rewrite_query(question: str) -> str:
    """Rewrite user question using corpus vocabulary for better retrieval."""
    try:
        corpus = get_corpus_index()
        if not corpus:
            return question
        index_lines = [
            f"- {e['doc_title']} ({e['classification']}): {e['summary'][:120]}"
            for e in corpus[:30]
        ]
        response = chat_completion(
            system_prompt=REWRITE_PROMPT.format(corpus_index="\n".join(index_lines)),
            user_message=question, temperature=0.0,
        )
        data = _extract_json(response)
        rewritten = data.get("rewritten_query", question)
        if rewritten and rewritten != question:
            logger.info("[retrieval] Query rewritten: '%s' → '%s'", question[:60], rewritten[:60])
            return rewritten
        return question
    except Exception:
        logger.warning("Query rewrite failed, using original", exc_info=True)
        return question


def _classify_intent(question: str) -> IntentClassification:
    """Classify request intent and decide retrieval route."""
    try:
        response = chat_completion(
            system_prompt=INTENT_PROMPT, user_message=question, temperature=0.0,
        )
        data = _extract_json(response)
        return IntentClassification(
            route=RetrievalRoute(data.get("route", "kb_only")),
            intent_type=data.get("intent_type", "general"),
            filters=data.get("filters", {}),
        )
    except Exception:
        logger.warning("Intent classification failed, defaulting to kb_only", exc_info=True)
        return IntentClassification(route=RetrievalRoute.kb_only, intent_type="general")


def _plan_queries(question: str) -> QueryPlan:
    """Generate 2-5 query variants for retrieval."""
    try:
        response = chat_completion(
            system_prompt=QUERY_PLAN_PROMPT, user_message=question, temperature=0.0,
        )
        data = _extract_json(response)
        variants = [
            QueryVariant(query=v["query"], query_type=v.get("query_type", "semantic"), k=CANDIDATE_K)
            for v in data.get("variants", [])
        ]
        if not any(v.query == question for v in variants):
            variants.insert(0, QueryVariant(query=question, query_type="semantic", k=CANDIDATE_K))
        return QueryPlan(variants=variants[:5], reasoning=data.get("reasoning", ""))
    except Exception:
        logger.warning("Query planning failed, using original question", exc_info=True)
        return QueryPlan(
            variants=[QueryVariant(query=question, query_type="semantic", k=CANDIDATE_K)],
            reasoning="Fallback: using original question",
        )


def _retrieve_candidates(query_plan: QueryPlan, filters: dict) -> list[CandidateChunk]:
    """Run vector/hybrid search for each query variant."""
    all_candidates: list[CandidateChunk] = []
    for variant in query_plan.variants:
        try:
            vector = generate_query_embedding(variant.query)
            use_hybrid = variant.query_type in ("keyword", "identifier")
            if use_hybrid:
                results = search_hybrid(variant.query, vector, k=variant.k, filters=filters or None)
            else:
                results = search_vectors(vector, k=variant.k, filters=filters or None)
            source = "hybrid" if use_hybrid else "vector"
            for r in results:
                all_candidates.append(CandidateChunk(
                    chunk_id=r["chunk_id"], doc_id=r["doc_id"], doc_title=r["doc_title"],
                    section_path=r["section_path"], text=r["text"],
                    score=1.0 / (1.0 + r.get("_distance", 1.0)), source=source,
                    source_filename=r["source_filename"], page=r.get("source_page"),
                ))
        except Exception:
            logger.warning("Retrieval failed for variant: %s", variant.query, exc_info=True)
    return all_candidates


def _fuse_and_dedup(candidates: list[CandidateChunk]) -> list[CandidateChunk]:
    """Reciprocal Rank Fusion + deduplication."""
    seen: dict[str, CandidateChunk] = {}
    chunk_ranks: dict[str, list[float]] = {}
    for rank, c in enumerate(candidates):
        if c.chunk_id not in seen:
            seen[c.chunk_id] = c
            chunk_ranks[c.chunk_id] = []
        chunk_ranks[c.chunk_id].append(rank + 1)
    rrf_k = 60
    rrf_scores = {cid: sum(1.0 / (rrf_k + r) for r in ranks) for cid, ranks in chunk_ranks.items()}
    fused = []
    for cid in sorted(rrf_scores, key=lambda x: rrf_scores[x], reverse=True):
        chunk = seen[cid]
        chunk.score = rrf_scores[cid]
        fused.append(chunk)
    return fused[:40]


# Step event type: ("step", label, status) or ("result", evidence_set, metrics)
StepEvent = tuple[str, ...]


def retrieve_with_steps(question: str) -> Generator[StepEvent]:
    """Generator that yields pipeline step events, then the final result.

    Yields: ("step", label, "active"|"done") for UI progress updates
    Final yield: ("result", evidence_set, metrics)
    """
    start = time.time()
    q = question.strip()

    yield ("step", "Classifying intent...", "active")
    intent = _classify_intent(q)
    yield ("step", "Classifying intent...", "done")
    logger.info("[retrieval] Intent: route=%s type=%s", intent.route.value, intent.intent_type)

    if intent.route == RetrievalRoute.no_retrieval:
        elapsed = (time.time() - start) * 1000
        yield ("result", EvidenceSet(evidence=[], is_sufficient=True), RetrievalMetrics(
            route="no_retrieval", queries_generated=0, total_candidates=0,
            post_fusion_candidates=0, post_rerank_count=0,
            evidence_count=0, retrieval_loops=0, latency_ms=elapsed,
        ))
        return

    yield ("step", "Rewriting query for corpus...", "active")
    q = _step2b_rewrite_query(q)
    yield ("step", "Rewriting query for corpus...", "done")

    all_candidates_count = 0
    fused_count = 0
    loops = 0
    evidence_set = EvidenceSet(evidence=[], is_sufficient=False)
    query_plan = None

    for loop in range(MAX_RETRIEVAL_LOOPS):
        loops = loop + 1
        yield ("step", "Planning search queries...", "active")
        query_plan = _plan_queries(q)
        yield ("step", "Planning search queries...", "done")

        n_queries = len(query_plan.variants)
        yield ("step", f"Searching documents ({n_queries} queries)...", "active")
        candidates = _retrieve_candidates(query_plan, intent.filters)
        all_candidates_count += len(candidates)
        yield ("step", f"Searching documents ({n_queries} queries)...", "done")

        yield ("step", f"Fusing {len(candidates)} candidates...", "active")
        fused = _fuse_and_dedup(candidates)
        fused_count = len(fused)
        yield ("step", f"Fusing {len(candidates)} candidates...", "done")

        yield ("step", "Cross-encoder reranking...", "active")
        ranked = rerank_candidates(q, fused)
        yield ("step", "Cross-encoder reranking...", "done")

        yield ("step", "Grading retrieval quality...", "active")
        crag_result = assess_and_correct(q, ranked)
        yield ("step", "Grading retrieval quality...", "done")

        yield ("step", "Validating evidence...", "active")
        evidence_set = validate_evidence(q, crag_result.evidence)
        if crag_result.correction_note:
            evidence_set.gap_description = (
                evidence_set.gap_description + " " + crag_result.correction_note
            ).strip()
        yield ("step", "Validating evidence...", "done")

        if evidence_set.is_sufficient or not evidence_set.gap_description:
            break
        q = f"{question} (also looking for: {evidence_set.gap_description})"

    elapsed = (time.time() - start) * 1000
    metrics = RetrievalMetrics(
        route=intent.route.value,
        queries_generated=len(query_plan.variants) if query_plan else 0,
        total_candidates=all_candidates_count, post_fusion_candidates=fused_count,
        post_rerank_count=len(evidence_set.evidence), evidence_count=len(evidence_set.evidence),
        retrieval_loops=loops, latency_ms=elapsed,
    )
    logger.info("Retrieval complete", extra={"metrics": metrics.model_dump()})
    yield ("result", evidence_set, metrics)


def retrieve(question: str) -> tuple[EvidenceSet, RetrievalMetrics]:
    """Run the full retrieval pipeline (non-streaming wrapper)."""
    for item in retrieve_with_steps(question):
        if item[0] == "result":
            return item[1], item[2]
    # Should never reach here
    return EvidenceSet(evidence=[], is_sufficient=False), RetrievalMetrics(
        route="error", queries_generated=0, total_candidates=0,
        post_fusion_candidates=0, post_rerank_count=0,
        evidence_count=0, retrieval_loops=0, latency_ms=0,
    )
