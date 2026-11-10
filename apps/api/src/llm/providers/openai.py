"""
OpenAI provider – standard OpenAI API implementation.
"""

from __future__ import annotations

from src.llm.providers.openai_compat import OpenAICompatibleLLM


class OpenAILLM(OpenAICompatibleLLM):
    """
    OpenAI LLM provider using the official OpenAI API.
    """

    def __init__(
        self,
        *,
        api_key: str,
        base_url: str = "https://api.openai.com/v1",
        model: str = "gpt-4.1-mini",
        default_temperature: float = 0.2,
        default_timeout: float = 60.0,
    ) -> None:
        super().__init__(
            base_url=base_url,
            api_key=api_key,
            model=model,
            provider="openai",
            default_temperature=default_temperature,
            default_timeout=default_timeout,
        )


def create_openai_llm(
    *,
    api_key: str,
    base_url: str = "https://api.openai.com/v1",
    model: str = "gpt-4.1-mini",
    default_temperature: float = 0.2,
    default_timeout: float = 60.0,
) -> OpenAILLM:
    """Factory helper – creates a standard OpenAI LLM provider instance."""
    return OpenAILLM(
        api_key=api_key,
        base_url=base_url,
        model=model,
        default_temperature=default_temperature,
        default_timeout=default_timeout,
    )
