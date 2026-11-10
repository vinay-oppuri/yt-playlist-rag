"""
Centralised application settings backed by pydantic-settings.

Reads from environment variables and falls back to ``apps/api/.env``
during development.  API keys are never logged or serialised.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Literal, Optional

from pydantic import SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application-wide configuration loaded from env vars / .env file."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ── LLM provider selection ──────────────────────────────────────────
    llm_provider: Literal["ollama", "openai", "gemini"] = "ollama"
    llm_model: str = "qwen3:8b"

    # ── Ollama (OpenAI-compatible) ──────────────────────────────────────
    ollama_base_url: str = "http://localhost:11434/v1"

    # ── OpenAI ──────────────────────────────────────────────────────────
    openai_api_key: Optional[SecretStr] = None
    openai_base_url: str = "https://api.openai.com/v1"

    # ── Google Gemini ───────────────────────────────────────────────────
    gemini_api_key: Optional[SecretStr] = None

    # ── Shared LLM defaults ─────────────────────────────────────────────
    llm_temperature: float = 0.2
    llm_timeout: float = 60.0  # seconds

    @field_validator("llm_provider", mode="before")
    @classmethod
    def _normalise_provider(cls, v: str) -> str:
        return v.strip().lower()


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return a cached singleton of the application settings."""
    return Settings()
