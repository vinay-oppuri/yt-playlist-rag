"""
LLM API routes.

  POST  /api/v1/llm/generate        – generate a text completion
  GET   /api/v1/llm/health           – lightweight config check
  GET   /api/v1/llm/connectivity     – deeper provider connectivity probe
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException

from src.llm.base import BaseLLM
from src.llm.exceptions import LLMError
from src.llm.factory import get_llm
from src.schemas import (
    LLMConnectivityResponse,
    LLMGenerateRequest,
    LLMGenerateResponse,
    LLMHealthResponse,
)

logger = logging.getLogger("yt_rag.api.llm")

router = APIRouter(prefix="/api/v1/llm", tags=["llm"])


@router.post("/generate", response_model=LLMGenerateResponse)
async def generate(
    body: LLMGenerateRequest,
    llm: BaseLLM = Depends(get_llm),
) -> LLMGenerateResponse:
    """Generate a text completion from the configured LLM provider."""
    try:
        text = await llm.generate(
            prompt=body.prompt,
            system_prompt=body.system_prompt,
        )
    except LLMError as exc:
        logger.warning("LLM generation failed: %s", exc)
        raise HTTPException(status_code=_status_for(exc), detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Unexpected error during LLM generation")
        raise HTTPException(
            status_code=500,
            detail="An internal error occurred during LLM generation.",
        ) from exc

    return LLMGenerateResponse(
        provider=llm.provider_name,
        model=llm.model_name,
        response=text,
    )


@router.get("/health", response_model=LLMHealthResponse)
async def health(
    llm: BaseLLM = Depends(get_llm),
) -> LLMHealthResponse:
    """Lightweight health check – reports configured provider and model."""
    return LLMHealthResponse(
        provider=llm.provider_name,
        model=llm.model_name,
        status="configured",
    )


@router.get("/connectivity", response_model=LLMConnectivityResponse)
async def connectivity(
    llm: BaseLLM = Depends(get_llm),
) -> LLMConnectivityResponse:
    """Probe the upstream LLM provider for connectivity."""
    reachable = await llm.check_connectivity()
    return LLMConnectivityResponse(
        provider=llm.provider_name,
        model=llm.model_name,
        reachable=reachable,
    )


# ── Helpers ─────────────────────────────────────────────────────────────

def _status_for(exc: LLMError) -> int:
    """Map domain exceptions to HTTP status codes."""
    from src.llm.exceptions import (
        LLMAuthenticationError,
        LLMConfigurationError,
        LLMConnectionError,
        LLMRateLimitError,
        LLMTimeoutError,
    )

    if isinstance(exc, LLMConfigurationError):
        return 500
    if isinstance(exc, LLMAuthenticationError):
        return 502
    if isinstance(exc, LLMConnectionError):
        return 502
    if isinstance(exc, LLMRateLimitError):
        return 429
    if isinstance(exc, LLMTimeoutError):
        return 504
    return 502
