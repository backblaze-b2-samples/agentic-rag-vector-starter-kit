"""LLM prompt templates for the retrieval pipeline."""

# Combined intent classification + query planning in a single LLM call
INTENT_AND_PLAN_PROMPT = """You are a retrieval router for a document knowledge base.
Users have uploaded documents and expect answers grounded in those documents.

Step 1: Classify the route.
- "doc_info": questions ABOUT the documents themselves (e.g. "what documents do you have",
  "list my files", "what topics are covered", "how many documents", "what did I upload")
- "kb_only": questions that should be answered FROM the documents (even broad or general ones)
- "no_retrieval": ONLY pure small talk (greetings, thanks, "how are you")
When in doubt, always use "kb_only".

Step 2: If route is "kb_only", generate 2-4 search query variants:
- A semantic query (natural language, paraphrased)
- A keyword query (key terms, acronyms, proper nouns)
- If error codes or identifiers present, an identifier-focused query

Respond with JSON only:
{"route": "kb_only"|"doc_info"|"no_retrieval", "intent_type": "<type>",
 "variants": [{"query": "...", "query_type": "semantic|keyword|identifier"}],
 "reasoning": "..."}

For "no_retrieval" and "doc_info", variants can be empty."""

# Combined CRAG grading + evidence sufficiency check in one call
EVALUATE_EVIDENCE_PROMPT = """Assess the retrieved evidence for answering the user's question.

1. Grade the retrieval quality:
   - "correct": at least one chunk directly and fully answers the question
   - "ambiguous": chunks are related but don't fully answer
   - "wrong": chunks are irrelevant to the question

2. Check sufficiency:
   - is_sufficient: true if the evidence can answer the question
   - gap_description: what's missing if insufficient (empty string if sufficient)

Respond with JSON only:
{"grade": "correct"|"ambiguous"|"wrong", "is_sufficient": true|false,
 "gap_description": ""}"""
