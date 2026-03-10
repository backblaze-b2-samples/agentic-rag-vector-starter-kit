"""LLM repo layer — LangChain wrapper for embeddings and chat.

All langchain SDK usage is confined to this module.
Supports OpenAI (default, one key for everything) and Anthropic (chat only).
"""

import functools
import logging

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI, OpenAIEmbeddings

from app.config import settings

logger = logging.getLogger(__name__)


@functools.lru_cache(maxsize=1)
def get_embeddings_model():
    """Return configured embedding model (always OpenAI)."""
    return OpenAIEmbeddings(
        model=settings.embedding_model,
        openai_api_key=settings.openai_api_key,
    )


@functools.lru_cache(maxsize=1)
def get_chat_model():
    """Return configured chat LLM based on llm_provider setting."""
    if settings.llm_provider == "anthropic":
        from langchain_anthropic import ChatAnthropic

        return ChatAnthropic(
            model=settings.llm_model,
            anthropic_api_key=settings.anthropic_api_key,
            max_tokens=4096,
        )
    # Default: OpenAI (same key as embeddings)
    return ChatOpenAI(
        model=settings.llm_model,
        openai_api_key=settings.openai_api_key,
        max_tokens=4096,
    )


def generate_embeddings(texts: list[str]) -> list[list[float]]:
    """Generate embeddings for a batch of texts.

    Returns list of float vectors, one per input text.
    """
    if not texts:
        return []
    model = get_embeddings_model()
    vectors = model.embed_documents(texts)
    logger.info("Generated embeddings", extra={"count": len(texts)})
    return vectors


def generate_query_embedding(query: str) -> list[float]:
    """Generate a single embedding for a search query."""
    if not query or not query.strip():
        raise ValueError("Query must be a non-empty string")
    model = get_embeddings_model()
    return model.embed_query(query)


def chat_completion(
    system_prompt: str,
    user_message: str,
    temperature: float = 0.0,
) -> str:
    """Run a single chat completion and return the text response."""
    model = get_chat_model()
    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=user_message),
    ]
    response = model.invoke(messages, temperature=temperature)
    # response.content can be a list of content blocks (Anthropic); extract text
    content = response.content
    if isinstance(content, list):
        return "".join(
            block if isinstance(block, str) else block.get("text", "")
            for block in content
        )
    return content


def chat_completion_stream(
    system_prompt: str,
    user_message: str,
    temperature: float = 0.3,
):
    """Stream a chat completion, yielding text chunks.

    Yields string chunks as they arrive from the LLM.
    """
    model = get_chat_model()
    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=user_message),
    ]
    for chunk in model.stream(messages, temperature=temperature):
        if chunk.content:
            yield chunk.content
