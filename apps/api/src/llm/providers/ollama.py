"""
Ollama provider – OpenAI-compatible LLM implementation for local Ollama.

Ollama exposes ``/v1/chat/completions`` with a dummy API key, so we
subclass :class:`OpenAICompatibleLLM` with the Ollama defaults.
"""

from __future__ import annotations

from src.llm.providers.openai_compat import OpenAICompatibleLLM


class OllamaLLM(OpenAICompatibleLLM):
    """
    Ollama LLM provider using the OpenAI-compatible endpoint.

    Default base_url: http://localhost:11434/v1
    Default api_key: "ollama"
    """

    def __init__(
        self,
        *,
        base_url: str = "http://localhost:11434/v1",
        model: str = "qwen3:8b",
        default_temperature: float = 0.2,
        default_timeout: float = 60.0,
    ) -> None:
        super().__init__(
            base_url=base_url,
            api_key="ollama",
            model=model,
            provider="ollama",
            default_temperature=default_temperature,
            default_timeout=default_timeout,
        )


def create_ollama_llm(
    *,
    base_url: str = "http://localhost:11434/v1",
    model: str = "qwen3:8b",
    default_temperature: float = 0.2,
    default_timeout: float = 60.0,
) -> OllamaLLM:
    """Factory helper – creates an Ollama LLM provider instance."""
    return OllamaLLM(
        base_url=base_url,
        model=model,
        default_temperature=default_temperature,
        default_timeout=default_timeout,
    )
