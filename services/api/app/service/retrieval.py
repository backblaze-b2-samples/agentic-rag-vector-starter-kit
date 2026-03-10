"""Agentic retrieval engine — 9-step pipeline from query to evidence.

Steps:
1. Parse inputs/constraints
2. Intent classification and routing
3. Query planning (2-5 variants)
4. Candidate retrieval (parallel vector search)
5. Fusion and deduplication (RRF scoring)
6. Reranking (LLM-based relevance judge) — see reranker.py
7. Evidence validation + gap handling — see reranker.py
8. Context construction (compact evidence pack)
9. Post-retrieval logging
"""

import json
import logging
import time

from app.repo import chat_completion, generate_query_embedding, search_vectors
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

_INTENT_PROMPT = """Classify the user's intent. Respond with JSON only.

If the question is purely conversational (greetings, thanks, small talk) or can be answered
without any document lookup, set route to "no_retrieval".
Otherwise set route to "kb_only".

Classify intent_type as one of: q_and_a, troubleshooting, policy, action, analytics, general.

{"route": "kb_only"|"no_retrieval", "intent_type": "<type>", "filters": {}}"""

_QUERY_PLAN_PROMPT = """Generate 2-5 search query variants to find relevant documents.
Each variant should approach the question differently:
- A semantic query (natural language, paraphrased)
- A keyword query (key terms, acronyms, proper nouns)
- If error codes or identifiers are present, an identifier-focused query

Respond with JSON only:
{"variants": [{"query": "...", "query_type": "semantic|keyword|identifier"}], "reasoning": "..."}"""

MAX_RETRIEVAL_LOOPS = 2
CANDIDATE_K = 30


def _step1_parse_inputs(question: str) -> dict:
    """Step 1: Parse inputs and constraints."""
    return {"question": question.strip()}


def _step2_classify_intent(question: str) -> IntentClassification:
    """Step 2: Classify request intent and decide retrieval route."""
    try:
        response = chat_completion(
            system_prompt=_INTENT_PROMPT,
            user_message=question,
            temperature=0.0,
        )
        data = json.loads(response.strip())
        return IntentClassification(
            route=RetrievalRoute(data.get("route", "kb_only")),
            intent_type=data.get("intent_type", "general"),
            filters=data.get("filters", {}),
        )
    except Exception:
        logger.warning("Intent classification failed, defaulting to kb_only", exc_info=True)
        return IntentClassification(
            route=RetrievalRoute.kb_only, intent_type="general",
        )


def _step3_plan_queries(question: str) -> QueryPlan:
    """Step 3: Generate 2-5 query variants for retrieval."""
    try:
        response = chat_completion(
            system_prompt=_QUERY_PLAN_PROMPT,
            user_message=question,
            temperature=0.0,
        )
        data = json.loads(response.strip())
        variants = [
            QueryVariant(
                query=v["query"],
                query_type=v.get("query_type", "semantic"),
                k=CANDIDATE_K,
            )
            for v in data.get("variants", [])
        ]
        # Always include the original question as a variant
        if not any(v.query == question for v in variants):
            variants.insert(0, QueryVariant(
                query=question, query_type="semantic", k=CANDIDATE_K,
            ))
        return QueryPlan(variants=variants[:5], reasoning=data.get("reasoning", ""))
    except Exception:
        logger.warning("Query planning failed, using original question", exc_info=True)
        return QueryPlan(
            variants=[QueryVariant(query=question, query_type="semantic", k=CANDIDATE_K)],
            reasoning="Fallback: using original question",
        )


def _step4_retrieve_candidates(
    query_plan: QueryPlan, filters: dict,
) -> list[CandidateChunk]:
    """Step 4: Run vector search for each query variant."""
    all_candidates: list[CandidateChunk] = []
    for variant in query_plan.variants:
        try:
            vector = generate_query_embedding(variant.query)
            results = search_vectors(vector, k=variant.k, filters=filters or None)
            for r in results:
                all_candidates.append(CandidateChunk(
                    chunk_id=r["chunk_id"],
                    doc_id=r["doc_id"],
                    doc_title=r["doc_title"],
                    section_path=r["section_path"],
                    text=r["text"],
                    score=1.0 / (1.0 + r.get("_distance", 1.0)),
                    source="vector",
                    source_filename=r["source_filename"],
                    page=r.get("source_page"),
                ))
        except Exception:
            logger.warning("Retrieval failed for variant: %s", variant.query, exc_info=True)
    return all_candidates


def _step5_fuse_and_dedup(candidates: list[CandidateChunk]) -> list[CandidateChunk]:
    """Step 5: Reciprocal Rank Fusion + deduplication."""
    seen: dict[str, CandidateChunk] = {}
    chunk_ranks: dict[str, list[float]] = {}

    for rank, candidate in enumerate(candidates):
        cid = candidate.chunk_id
        if cid not in seen:
            seen[cid] = candidate
            chunk_ranks[cid] = []
        chunk_ranks[cid].append(rank + 1)

    # RRF scoring: sum of 1/(k+rank) across all rankings
    rrf_k = 60
    rrf_scores: dict[str, float] = {}
    for cid, ranks in chunk_ranks.items():
        rrf_scores[cid] = sum(1.0 / (rrf_k + r) for r in ranks)

    sorted_ids = sorted(rrf_scores, key=lambda x: rrf_scores[x], reverse=True)
    fused = []
    for cid in sorted_ids:
        chunk = seen[cid]
        chunk.score = rrf_scores[cid]
        fused.append(chunk)
    return fused[:40]


def retrieve(question: str) -> tuple[EvidenceSet, RetrievalMetrics]:
    """Run the full agentic retrieval pipeline.

    Returns (evidence_set, metrics) tuple.
    """
    start = time.time()
    inputs = _step1_parse_inputs(question)
    q = inputs["question"]

    # Step 2: Intent classification
    intent = _step2_classify_intent(q)
    if intent.route == RetrievalRoute.no_retrieval:
        elapsed = (time.time() - start) * 1000
        return (
            EvidenceSet(evidence=[], is_sufficient=True),
            RetrievalMetrics(
                route="no_retrieval", queries_generated=0, total_candidates=0,
                post_fusion_candidates=0, post_rerank_count=0,
                evidence_count=0, retrieval_loops=0, latency_ms=elapsed,
            ),
        )

    # Retrieval loop (max 2 iterations for gap handling)
    all_candidates_count = 0
    fused_count = 0
    loops = 0
    evidence_set = EvidenceSet(evidence=[], is_sufficient=False)
    query_plan = None

    for loop in range(MAX_RETRIEVAL_LOOPS):
        loops = loop + 1
        query_plan = _step3_plan_queries(q)
        candidates = _step4_retrieve_candidates(query_plan, intent.filters)
        all_candidates_count += len(candidates)
        fused = _step5_fuse_and_dedup(candidates)
        fused_count = len(fused)

        # Steps 6-7: Rerank and validate (delegated to reranker module)
        ranked = rerank_candidates(q, fused)
        evidence_set = validate_evidence(q, ranked)

        if evidence_set.is_sufficient or not evidence_set.gap_description:
            break
        q = f"{question} (also looking for: {evidence_set.gap_description})"
        logger.info("Retrieval loop %d: refining query for gaps", loops)

    # Step 9: Metrics
    elapsed = (time.time() - start) * 1000
    metrics = RetrievalMetrics(
        route=intent.route.value,
        queries_generated=len(query_plan.variants) if query_plan else 0,
        total_candidates=all_candidates_count,
        post_fusion_candidates=fused_count,
        post_rerank_count=len(evidence_set.evidence),
        evidence_count=len(evidence_set.evidence),
        retrieval_loops=loops,
        latency_ms=elapsed,
    )
    logger.info("Retrieval complete", extra={"metrics": metrics.model_dump()})
    return evidence_set, metrics
