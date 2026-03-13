"""Agentic retrieval engine — optimized multi-step pipeline.

Intent+plan (1 LLM call) → batch embed → retrieve → fuse → rerank
(cross-encoder) → evaluate (1 LLM call) → metrics.
Optimized from 6+ serial LLM calls to 2 LLM + 1 embedding batch.
"""

import json
import logging
import re
import time
from collections.abc import Generator

from app.repo import (
    chat_completion,
    generate_embeddings,
    generate_query_embedding,
    get_corpus_index,
    search_hybrid,
    search_vectors,
)
from app.service._retrieval_prompts import EVALUATE_EVIDENCE_PROMPT, INTENT_AND_PLAN_PROMPT
from app.service.reranker import rerank_candidates
from app.types import (
    CandidateChunk,
    EvidenceSet,
    IntentClassification,
    QueryPlan,
    QueryVariant,
    RankedEvidence,
    RetrievalMetrics,
    RetrievalRoute,
)

logger = logging.getLogger(__name__)

MAX_RETRIEVAL_LOOPS = 2
CANDIDATE_K = 20


def _extract_json(text: str) -> dict:
    """Parse JSON from LLM output, stripping markdown code fences if present."""
    cleaned = text.strip()
    cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
    cleaned = re.sub(r"\s*```$", "", cleaned)
    return json.loads(cleaned.strip())


def _classify_and_plan(question: str) -> tuple[IntentClassification, QueryPlan]:
    """Single LLM call: classify intent AND generate query variants."""
    try:
        response = chat_completion(
            system_prompt=INTENT_AND_PLAN_PROMPT, user_message=question, temperature=0.0,
        )
        data = _extract_json(response)
        intent = IntentClassification(
            route=RetrievalRoute(data.get("route", "kb_only")),
            intent_type=data.get("intent_type", "general"),
            filters=data.get("filters", {}),
        )
        variants = [
            QueryVariant(query=v["query"], query_type=v.get("query_type", "semantic"), k=CANDIDATE_K)
            for v in data.get("variants", [])
        ]
        # Ensure original question is always included
        if variants and not any(v.query == question for v in variants):
            variants.insert(0, QueryVariant(query=question, query_type="semantic", k=CANDIDATE_K))
        plan = QueryPlan(variants=variants[:4], reasoning=data.get("reasoning", ""))
        return intent, plan
    except Exception:
        logger.warning("Intent+plan failed, defaulting to kb_only", exc_info=True)
        intent = IntentClassification(route=RetrievalRoute.kb_only, intent_type="general")
        plan = QueryPlan(
            variants=[QueryVariant(query=question, query_type="semantic", k=CANDIDATE_K)],
            reasoning="Fallback",
        )
        return intent, plan


def _retrieve_candidates_batched(query_plan: QueryPlan, filters: dict) -> list[CandidateChunk]:
    """Batch all variant embeddings into one API call, then search."""
    variants = query_plan.variants
    if not variants:
        return []

    # Batch embed all queries at once (1 API call instead of N)
    queries = [v.query for v in variants]
    try:
        vectors = generate_embeddings(queries)
    except Exception:
        logger.warning("Batch embedding failed, falling back to single", exc_info=True)
        vectors = [generate_query_embedding(q) for q in queries]

    all_candidates: list[CandidateChunk] = []
    for variant, vector in zip(variants, vectors, strict=True):
        try:
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
    return fused[:30]


def _evaluate_evidence(question: str, evidence: list[RankedEvidence]) -> EvidenceSet:
    """Single LLM call: CRAG grading + sufficiency check combined."""
    if not evidence:
        return EvidenceSet(evidence=[], is_sufficient=False, gap_description="No relevant evidence found")

    evidence_text = "\n---\n".join(
        f"[{i+1}] {e.doc_title} > {e.section_path}\n{e.text[:400]}"
        for i, e in enumerate(evidence[:8])
    )
    try:
        response = chat_completion(
            system_prompt=EVALUATE_EVIDENCE_PROMPT,
            user_message=f"Question: {question}\n\nEvidence:\n{evidence_text}",
            temperature=0.0,
        )
        data = _extract_json(response)
        grade = data.get("grade", "ambiguous")

        # If grade is "wrong", strip evidence
        if grade == "wrong":
            logger.info("[retrieval] Grade=wrong — discarding evidence")
            return EvidenceSet(
                evidence=[], is_sufficient=False,
                gap_description="Retrieved documents were not relevant. "
                "Answer based on general knowledge or indicate you cannot answer.",
            )
        return EvidenceSet(
            evidence=evidence,
            is_sufficient=data.get("is_sufficient", True),
            gap_description=data.get("gap_description", ""),
        )
    except Exception:
        logger.warning("Evidence evaluation failed, using evidence as-is", exc_info=True)
        return EvidenceSet(evidence=evidence, is_sufficient=len(evidence) >= 2)


def _build_doc_info_evidence() -> list[RankedEvidence]:
    """Convert corpus index into evidence so the LLM can describe documents."""
    corpus = get_corpus_index()
    return [
        RankedEvidence(
            chunk_id=doc["doc_id"], doc_id=doc["doc_id"],
            doc_title=doc["doc_title"], section_path="Document Overview",
            text=f"Document: {doc['doc_title']}\nType: {doc['classification']}\nSummary: {doc['summary']}",
            relevance_score=1.0, source_filename=doc["doc_title"],
        )
        for doc in corpus
    ]


# Step event type: ("step", label, status) or ("result", evidence_set, metrics)
StepEvent = tuple[str, ...]


def retrieve_with_steps(question: str) -> Generator[StepEvent]:
    """Optimized retrieval: 2 LLM calls + 1 batch embedding instead of 6+ calls."""
    start = time.time()
    q = question.strip()

    # Step 1: Combined intent classification + query planning (1 LLM call)
    yield ("step", "Analyzing question...", "active")
    intent, query_plan = _classify_and_plan(q)
    yield ("step", "Analyzing question...", "done")
    logger.info("[retrieval] Intent: route=%s type=%s variants=%d",
                intent.route.value, intent.intent_type, len(query_plan.variants))

    if intent.route == RetrievalRoute.no_retrieval:
        elapsed = (time.time() - start) * 1000
        yield ("result", EvidenceSet(evidence=[], is_sufficient=True), RetrievalMetrics(
            route="no_retrieval", queries_generated=0, total_candidates=0,
            post_fusion_candidates=0, post_rerank_count=0,
            evidence_count=0, retrieval_loops=0, latency_ms=elapsed,
        ))
        return

    if intent.route == RetrievalRoute.doc_info:
        yield ("step", "Loading document inventory...", "active")
        evidence = _build_doc_info_evidence()
        yield ("step", "Loading document inventory...", "done")
        elapsed = (time.time() - start) * 1000
        yield ("result", EvidenceSet(evidence=evidence, is_sufficient=len(evidence) > 0), RetrievalMetrics(
            route="doc_info", queries_generated=0, total_candidates=len(evidence),
            post_fusion_candidates=0, post_rerank_count=len(evidence),
            evidence_count=len(evidence), retrieval_loops=0, latency_ms=elapsed,
        ))
        return

    # Retrieval loop (usually 1 iteration)
    all_candidates_count = 0
    fused_count = 0
    loops = 0
    evidence_set = EvidenceSet(evidence=[], is_sufficient=False)

    for loop in range(MAX_RETRIEVAL_LOOPS):
        loops = loop + 1
        n_q = len(query_plan.variants)

        # Step 2: Batch embed + search (1 embedding API call)
        yield ("step", f"Searching ({n_q} queries)...", "active")
        candidates = _retrieve_candidates_batched(query_plan, intent.filters)
        all_candidates_count += len(candidates)
        yield ("step", f"Searching ({n_q} queries)...", "done")

        if not candidates:
            logger.info("[retrieval] No candidates found")
            break

        # Step 3: Fuse + rerank (local, fast)
        yield ("step", "Ranking results...", "active")
        fused = _fuse_and_dedup(candidates)
        fused_count = len(fused)
        ranked = rerank_candidates(q, fused)
        yield ("step", "Ranking results...", "done")

        # Step 4: Evaluate evidence — combined CRAG + validation (1 LLM call)
        try:
            yield ("step", "Evaluating evidence...", "active")
            evidence_set = _evaluate_evidence(q, ranked)
            yield ("step", "Evaluating evidence...", "done")
        except Exception:
            logger.warning("Evidence evaluation failed", exc_info=True)
            evidence_set = EvidenceSet(evidence=ranked, is_sufficient=len(ranked) >= 1)
            yield ("step", "Evaluating evidence...", "done")

        if evidence_set.is_sufficient or not evidence_set.gap_description:
            break
        # Retry with refined query
        q = f"{question} (also looking for: {evidence_set.gap_description})"
        intent, query_plan = _classify_and_plan(q)

    elapsed = (time.time() - start) * 1000
    metrics = RetrievalMetrics(
        route=intent.route.value,
        queries_generated=len(query_plan.variants),
        total_candidates=all_candidates_count, post_fusion_candidates=fused_count,
        post_rerank_count=len(evidence_set.evidence), evidence_count=len(evidence_set.evidence),
        retrieval_loops=loops, latency_ms=elapsed,
    )
    logger.info("Retrieval complete in %.0fms", elapsed)
    yield ("result", evidence_set, metrics)


def retrieve(question: str) -> tuple[EvidenceSet, RetrievalMetrics]:
    """Run the full retrieval pipeline (non-streaming wrapper)."""
    for item in retrieve_with_steps(question):
        if item[0] == "result":
            return item[1], item[2]
    return EvidenceSet(evidence=[], is_sufficient=False), RetrievalMetrics(
        route="error", queries_generated=0, total_candidates=0,
        post_fusion_candidates=0, post_rerank_count=0,
        evidence_count=0, retrieval_loops=0, latency_ms=0,
    )
