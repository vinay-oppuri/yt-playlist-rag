"""
LLM factory – inspects configuration and returns the correct provider.

The returned instance is a module-level singleton so that the underlying
HTTP client is reused across requests.
"""

from __future__ import annotations

import logging
from threading import Lock

from src.core.config import get_settings
from src.llm.base import BaseLLM
from src.llm.exceptions import LLMConfigurationError

logger = logging.getLogger("yt_rag.llm.factory")

_instance: BaseLLM | None = None
_lock = Lock()


def get_llm() -> BaseLLM:
    """
    Return a singleton :class:`BaseLLM` based on the current settings.

    Thread-safe; the first call creates the instance, subsequent calls
    return the cached object.  Safe to use as a FastAPI dependency
    (``Depends(get_llm)``).
    """
    global _instance
    if _instance is not None:
        return _instance

    with _lock:
        # Double-checked locking
        if _instance is not None:  # pragma: no cover
            return _instance
        _instance = _build_llm()
        return _instance


def _build_llm() -> BaseLLM:
    """Construct the correct LLM provider from settings."""
    settings = get_settings()
    provider = settings.llm_provider

    if provider == "ollama":
        from src.llm.providers.ollama import create_ollama_llm

        return create_ollama_llm(
            base_url=settings.ollama_base_url,
            model=settings.llm_model,
            default_temperature=settings.llm_temperature,
            default_timeout=settings.llm_timeout,
        )

    if provider == "openai":
        if not settings.openai_api_key:
            raise LLMConfigurationError(
                "LLM_PROVIDER is 'openai' but OPENAI_API_KEY is not set. "
                "Add OPENAI_API_KEY to your .env file.",
                provider="openai",
            )
        from src.llm.providers.openai import create_openai_llm

        return create_openai_llm(
            api_key=settings.openai_api_key.get_secret_value(),
            base_url=settings.openai_base_url,
            model=settings.llm_model,
            default_temperature=settings.llm_temperature,
            default_timeout=settings.llm_timeout,
        )

    if provider == "gemini":
        if not settings.gemini_api_key:
            raise LLMConfigurationError(
                "LLM_PROVIDER is 'gemini' but GEMINI_API_KEY is not set. "
                "Add GEMINI_API_KEY to your .env file.",
                provider="gemini",
            )
        from src.llm.providers.gemini import GeminiLLM

        return GeminiLLM(
            api_key=settings.gemini_api_key.get_secret_value(),
            model=settings.llm_model,
            default_temperature=settings.llm_temperature,
            default_timeout=settings.llm_timeout,
        )

    raise LLMConfigurationError(
        f"Unknown LLM_PROVIDER '{provider}'. "
        f"Supported values: ollama, openai, gemini.",
        provider=provider,
    )
