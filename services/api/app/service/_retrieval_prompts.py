"""LLM prompt templates for the retrieval pipeline."""

INTENT_PROMPT = """Classify the user's intent. Respond with JSON only.

If the question is purely conversational (greetings, thanks, small talk) or can be answered
without any document lookup, set route to "no_retrieval".
Otherwise set route to "kb_only".

Classify intent_type as one of: q_and_a, troubleshooting, policy, action, analytics, general.

{"route": "kb_only"|"no_retrieval", "intent_type": "<type>", "filters": {}}"""

QUERY_PLAN_PROMPT = """Generate 2-5 search query variants to find relevant documents.
Each variant should approach the question differently:
- A semantic query (natural language, paraphrased)
- A keyword query (key terms, acronyms, proper nouns)
- If error codes or identifiers are present, an identifier-focused query

Respond with JSON only:
{"variants": [{"query": "...", "query_type": "semantic|keyword|identifier"}], "reasoning": "..."}"""

REWRITE_PROMPT = """You are a search query rewriter for a document knowledge base.
Given the user's question and the available documents, rewrite the question to
better match the vocabulary and terminology in the corpus. Keep the original
intent. If no rewrite improves the query, return the original unchanged.

Available documents:
{corpus_index}

Respond with JSON only: {{"rewritten_query": "...", "reasoning": "..."}}}"""
