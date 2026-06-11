"""GET /api/catalog — providers and their default models."""

from __future__ import annotations

from fastapi import APIRouter

from app.infrastructure.providers.model_list import FALLBACK_MODELS
from app.infrastructure.providers.registry import PROVIDER_LABELS
from backend.schemas import CatalogResponse, ProviderInfo

router = APIRouter()

_PROVIDER_KEY_ENV: dict[str, str] = {
    "openai": "OPENAI_API_KEY",
    "anthropic": "ANTHROPIC_API_KEY",
    "gemini": "GEMINI_API_KEY",
    "openaicompatible": "OPENAICOMPATIBLE_API_KEY",
    "opencode": "OPENCODE_GO_API_KEY",
}

_PROVIDER_DEFAULT_MODEL: dict[str, str] = {
    "openai": "gpt-4o-mini",
    "anthropic": "claude-3-haiku-20240307",
    "gemini": "gemini/gemini-2.0-flash",
    "ollama": "ollama/llama3",
    "litellm": "gpt-4o-mini",
    "openaicompatible": "gpt-4o-mini",
    "opencode": "deepseek-v4-flash",
}

_ORDERED: list[str] = [
    "google",
    "openai",
    "anthropic",
    "gemini",
    "ollama",
    "litellm",
    "openaicompatible",
    "opencode",
]


@router.get("/catalog/providers", response_model=CatalogResponse)
def get_providers() -> CatalogResponse:
    providers: list[ProviderInfo] = []
    for pid in _ORDERED:
        providers.append(
            ProviderInfo(
                id=pid,
                label=PROVIDER_LABELS.get(pid, pid.title()),
                requires_key=pid in _PROVIDER_KEY_ENV,
                key_env=_PROVIDER_KEY_ENV.get(pid),
                default_model=_PROVIDER_DEFAULT_MODEL.get(pid),
                models=list(FALLBACK_MODELS.get(pid, [])),
            )
        )
    return CatalogResponse(providers=providers)
