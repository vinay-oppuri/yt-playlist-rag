"""Abstract base class for all LLM providers."""

from __future__ import annotations

from abc import ABC, abstractmethod


class BaseLLM(ABC):
    """
    Minimal async interface every LLM provider must implement.

    The contract is intentionally narrow so the rest of the application
    depends only on ``generate()`` and never on provider-specific details.

    Designed for future extension:
      - ``generate_stream()`` for token-by-token streaming
      - ``generate_structured()`` for JSON-mode / structured output
    """

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Canonical lowercase name of the provider (e.g. ``'ollama'``)."""
        ...

    @property
    @abstractmethod
    def model_name(self) -> str:
        """Model identifier as configured (e.g. ``'qwen3:8b'``)."""
        ...

    @abstractmethod
    async def generate(
        self,
        prompt: str,
        system_prompt: str | None = None,
        *,
        temperature: float | None = None,
        timeout: float | None = None,
    ) -> str:
        """
        Generate a text completion.

        Parameters
        ----------
        prompt:
            The user message / instruction.
        system_prompt:
            Optional system-level instruction prepended to the conversation.
        temperature:
            Sampling temperature override; ``None`` uses the provider default.
        timeout:
            Per-request timeout in seconds; ``None`` uses the provider default.

        Returns
        -------
        str
            The generated text (first choice, stripped of whitespace).
        """
        ...

    async def check_connectivity(self) -> bool:
        """
        Lightweight connectivity / readiness probe.

        Default implementation returns ``True``; providers may override to
        ping the upstream API without performing a full generation.
        """
        return True
