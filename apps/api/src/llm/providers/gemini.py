"""
Google Gemini LLM provider.

Uses the official ``google-genai`` SDK (``google.genai``) with the
async API (``client.aio.models.generate_content``).
"""

from __future__ import annotations

import logging

from google import genai
from google.genai import types

from src.llm.base import BaseLLM
from src.llm.exceptions import (
    LLMAuthenticationError,
    LLMConnectionError,
    LLMError,
    LLMProviderError,
    LLMRateLimitError,
    LLMTimeoutError,
)

logger = logging.getLogger("yt_rag.llm.gemini")


class GeminiLLM(BaseLLM):
    """
    Async LLM provider backed by the Google Gemini API.

    Parameters
    ----------
    api_key:
        Gemini API key.
    model:
        Model name (e.g. ``gemini-2.5-flash``).
    default_temperature:
        Default sampling temperature.
    default_timeout:
        Default per-request timeout in seconds.
    """

    def __init__(
        self,
        *,
        api_key: str,
        model: str = "gemini-2.5-flash",
        default_temperature: float = 0.2,
        default_timeout: float = 60.0,
    ) -> None:
        self._model = model
        self._default_temperature = default_temperature
        self._default_timeout = default_timeout
        self._client = genai.Client(api_key=api_key)
        logger.info("Initialised Gemini LLM provider  model=%s", model)

    # ── BaseLLM interface ───────────────────────────────────────────────

    @property
    def provider_name(self) -> str:
        return "gemini"

    @property
    def model_name(self) -> str:
        return self._model

    async def generate(
        self,
        prompt: str,
        system_prompt: str | None = None,
        *,
        temperature: float | None = None,
        timeout: float | None = None,
    ) -> str:
        config_kwargs: dict = {
            "temperature": temperature if temperature is not None else self._default_temperature,
        }
        if system_prompt:
            config_kwargs["system_instruction"] = system_prompt

        http_options = types.HttpOptions(
            timeout=int(
                (timeout if timeout is not None else self._default_timeout) * 1000
            ),
        )

        try:
            response = await self._client.aio.models.generate_content(
                model=self._model,
                contents=prompt,
                config=types.GenerateContentConfig(**config_kwargs, http_options=http_options),
            )
        except Exception as exc:
            raise self._map_error(exc) from exc

        return (response.text or "").strip()

    async def check_connectivity(self) -> bool:
        """List models as a lightweight connectivity check."""
        try:
            # Use async list; just consume one page
            async for _ in self._client.aio.models.list(config=types.ListModelsConfig(page_size=1)):
                break
            return True
        except Exception:
            logger.debug("Gemini connectivity check failed", exc_info=True)
            return False

    # ── Helpers ─────────────────────────────────────────────────────────

    def _map_error(self, exc: Exception) -> LLMError:
        """Translate google-genai errors into our domain exceptions."""
        msg = str(exc).lower()

        # The google-genai SDK raises generic exceptions; inspect the
        # message and/or type name to classify.
        if "timeout" in msg or "deadline" in msg:
            return LLMTimeoutError(
                "Gemini request timed out", provider="gemini"
            )
        if "401" in msg or "unauthenticated" in msg or "api key" in msg:
            return LLMAuthenticationError(
                "Gemini authentication failed – check GEMINI_API_KEY",
                provider="gemini",
            )
        if "429" in msg or "resource_exhausted" in msg or "rate" in msg:
            return LLMRateLimitError(
                "Gemini rate limit exceeded – try again later",
                provider="gemini",
            )
        if "connect" in msg or "resolve" in msg or "unreachable" in msg:
            return LLMConnectionError(
                "Cannot reach the Gemini API", provider="gemini"
            )

        return LLMProviderError(
            f"Gemini API error: {exc}", provider="gemini"
        )
