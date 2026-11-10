"""
OpenAI-compatible LLM provider.

This provider works with *any* server that exposes the OpenAI
``/v1/chat/completions`` API, including:

  - OpenAI itself
  - Ollama (``http://localhost:11434/v1``)
  - vLLM, LM Studio, LocalAI, etc.

Ollama and OpenAI share this implementation; only the ``base_url``
and ``api_key`` differ.
"""

from __future__ import annotations

import logging
from typing import Optional

from openai import AsyncOpenAI, APIConnectionError, APIStatusError, APITimeoutError

from src.llm.base import BaseLLM
from src.llm.exceptions import (
    LLMAuthenticationError,
    LLMConnectionError,
    LLMError,
    LLMProviderError,
    LLMRateLimitError,
    LLMTimeoutError,
)

logger = logging.getLogger("yt_rag.llm.openai_compat")


class OpenAICompatibleLLM(BaseLLM):
    """
    Async LLM provider backed by the ``openai`` Python SDK.

    Parameters
    ----------
    base_url:
        API base URL (e.g. ``https://api.openai.com/v1``).
    api_key:
        API key / token (use ``"ollama"`` for local Ollama).
    model:
        Model name to request (e.g. ``gpt-4.1-mini``, ``qwen3:8b``).
    provider:
        Display name surfaced in health / response metadata.
    default_temperature:
        Default sampling temperature.
    default_timeout:
        Default per-request timeout in seconds.
    """

    def __init__(
        self,
        *,
        base_url: str,
        api_key: str,
        model: str,
        provider: str = "openai",
        default_temperature: float = 0.2,
        default_timeout: float = 60.0,
    ) -> None:
        self._provider = provider
        self._model = model
        self._default_temperature = default_temperature
        self._default_timeout = default_timeout
        self._client = AsyncOpenAI(
            base_url=base_url,
            api_key=api_key,
            timeout=default_timeout,
        )
        logger.info(
            "Initialised %s LLM provider  model=%s  base_url=%s",
            provider,
            model,
            base_url,
        )

    # ── BaseLLM interface ───────────────────────────────────────────────

    @property
    def provider_name(self) -> str:
        return self._provider

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
        messages: list[dict[str, str]] = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        try:
            response = await self._client.chat.completions.create(
                model=self._model,
                messages=messages,
                temperature=temperature if temperature is not None else self._default_temperature,
                timeout=timeout if timeout is not None else self._default_timeout,
            )
        except APITimeoutError as exc:
            raise LLMTimeoutError(
                f"{self._provider} request timed out",
                provider=self._provider,
            ) from exc
        except APIConnectionError as exc:
            raise LLMConnectionError(
                f"Cannot reach {self._provider} at {self._client.base_url}",
                provider=self._provider,
            ) from exc
        except APIStatusError as exc:
            raise self._map_status_error(exc) from exc

        choice = response.choices[0] if response.choices else None
        if choice is None or choice.message.content is None:
            return ""
        return choice.message.content.strip()

    async def check_connectivity(self) -> bool:
        """Ping by listing models; cheap and doesn't burn tokens."""
        try:
            await self._client.models.list()
            return True
        except Exception:
            logger.debug("%s connectivity check failed", self._provider, exc_info=True)
            return False

    # ── Helpers ─────────────────────────────────────────────────────────

    def _map_status_error(self, exc: APIStatusError) -> LLMError:
        status = exc.status_code
        if status == 401:
            return LLMAuthenticationError(
                f"{self._provider} authentication failed – check your API key",
                provider=self._provider,
            )
        if status == 404:
            return LLMProviderError(
                f"{self._provider} model '{self._model}' not found – "
                f"is the model installed / available?",
                provider=self._provider,
            )
        if status == 429:
            return LLMRateLimitError(
                f"{self._provider} rate limit exceeded – try again later",
                provider=self._provider,
            )
        return LLMProviderError(
            f"{self._provider} API error (HTTP {status})",
            provider=self._provider,
        )
