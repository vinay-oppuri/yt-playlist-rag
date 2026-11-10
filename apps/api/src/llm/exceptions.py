"""Domain-specific exceptions for the LLM layer."""

from __future__ import annotations


class LLMError(Exception):
    """Base exception for all LLM-related errors."""

    def __init__(self, message: str, *, provider: str = "unknown") -> None:
        self.provider = provider
        super().__init__(message)


class LLMConfigurationError(LLMError):
    """Raised when the LLM layer is misconfigured (wrong provider, missing key)."""


class LLMConnectionError(LLMError):
    """Raised when the upstream LLM service cannot be reached."""


class LLMAuthenticationError(LLMError):
    """Raised when authentication with the LLM provider fails."""


class LLMRateLimitError(LLMError):
    """Raised when the provider returns a rate-limit / quota error."""


class LLMTimeoutError(LLMError):
    """Raised when a provider request exceeds the configured timeout."""


class LLMProviderError(LLMError):
    """Catch-all for other provider-side errors."""
