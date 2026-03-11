"""Document classification — categorize documents via LLM."""

import json
import logging
import re

from app.repo import chat_completion
from app.types import DocumentClassification

logger = logging.getLogger(__name__)

_CLASSIFICATION_PROMPT = """You are a document classifier. Given a text excerpt, classify it into exactly one category.

Categories:
- policy: Rules, guidelines, compliance documents
- procedure: Step-by-step instructions, SOPs, runbooks
- reference: API docs, specs, data dictionaries
- tutorial: Learning materials, guides, walkthroughs
- faq: Frequently asked questions
- troubleshooting: Error resolution, debugging guides
- api_docs: API reference, endpoint documentation
- general: Anything that doesn't fit the above

Respond with JSON only: {"classification": "<category>", "confidence": <0.0-1.0>}"""


def classify_document(text_sample: str) -> DocumentClassification:
    """Classify a document based on a text sample (first ~2000 chars).

    Uses LLM to determine the document category.
    Falls back to 'general' on any error.
    """
    # Use first 2000 chars as representative sample
    sample = text_sample[:2000]

    try:
        response = chat_completion(
            system_prompt=_CLASSIFICATION_PROMPT,
            user_message=f"Classify this document:\n\n{sample}",
            temperature=0.0,
        )

        # Parse JSON response (strip markdown fences if present)
        cleaned = re.sub(r"^```(?:json)?\s*", "", response.strip())
        cleaned = re.sub(r"\s*```$", "", cleaned)
        result = json.loads(cleaned.strip())
        classification = result.get("classification", "general")

        # Validate against enum
        try:
            return DocumentClassification(classification)
        except ValueError:
            logger.warning("Unknown classification: %s", classification)
            return DocumentClassification.general

    except Exception:
        logger.warning("Classification failed, defaulting to general", exc_info=True)
        return DocumentClassification.general
