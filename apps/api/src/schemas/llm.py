"""Request / response schemas for the LLM endpoints."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class LLMGenerateRequest(BaseModel):
    """POST /api/v1/llm/generate request body."""

    model_config = ConfigDict(str_strip_whitespace=True)

    prompt: str = Field(
        ...,
        min_length=1,
        max_length=8000,
        description="User prompt / instruction.",
    )
    system_prompt: str | None = Field(
        default=None,
        max_length=4000,
        description="Optional system-level instruction.",
    )


class LLMGenerateResponse(BaseModel):
    """POST /api/v1/llm/generate response body."""

    provider: str
    model: str
    response: str


class LLMHealthResponse(BaseModel):
    """GET /api/v1/llm/health response body."""

    provider: str
    model: str
    status: str


class LLMConnectivityResponse(BaseModel):
    """GET /api/v1/llm/connectivity response brain/probe."""

    provider: str
    model: str
    reachable: bool
