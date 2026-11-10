"""
High-level LLM service – the recommended entry point for application code.

Usage::

    from src.llm import LLMService

    service = LLMService()
    response = await service.generate(
        prompt="Explain this security event",
        system_prompt="You are a cybersecurity analyst.",
    )
"""

from __future__ import annotations

import logging

from src.llm.base import BaseLLM
from src.llm.factory import get_llm

logger = logging.getLogger("yt_rag.llm.service")


class LLMService:
    """
    Thin facade around the configured :class:`BaseLLM` provider.

    Exists so that application code can depend on a single import
    (``LLMService``) and stay decoupled from the factory / DI wiring.
    """

    def __init__(self, llm: BaseLLM | None = None) -> None:
        self._llm = llm or get_llm()

    @property
    def provider(self) -> str:
        return self._llm.provider_name

    @property
    def model(self) -> str:
        return self._llm.model_name

    async def generate(
        self,
        prompt: str,
        system_prompt: str | None = None,
        *,
        temperature: float | None = None,
        timeout: float | None = None,
    ) -> str:
        """Delegate to the underlying provider."""
        return await self._llm.generate(
            prompt,
            system_prompt,
            temperature=temperature,
            timeout=timeout,
        )

    async def check_connectivity(self) -> bool:
        """Delegate to the underlying provider's connectivity check."""
        return await self._llm.check_connectivity()
