"""Provider factory — resolves provider name to a TranslationProvider instance.

Uses the PROVIDER_FACTORIES registry from infrastructure.providers.registry
so built-in and third-party providers are discoverable without hard-coding.
"""

from __future__ import annotations

from loguru import logger

from ...application.ports import TranslationProvider
from .registry import PROVIDER_FACTORIES


def get_translator_service(
    provider: str,
    source_lang: str,
    target_lang: str,
    capitalize: bool = True,
    max_retries: int = 3,
    model: str | None = None,
    chunk_size: int | None = None,
    max_concurrent_chunks: int = 4,
    chunk_token_budget: int = 3500,
    chunk_max_text_length: int = 200,
    chunk_mode: str = "auto",
    *,
    source_lang_display: str | None = None,
    target_lang_display: str | None = None,
    glossary: dict[str, str] | None = None,
) -> TranslationProvider:
    """Resolve *provider* name to a TranslationProvider instance.

    Looks up the provider in PROVIDER_FACTORIES, which is populated by
    the @register_provider decorator at import time.
    """
    provider_lower = provider.lower()
    factory = PROVIDER_FACTORIES.get(provider_lower)

    if factory is None:
        raise ValueError(
            f"Unsupported translation provider: {provider}. Supported: {', '.join(sorted(PROVIDER_FACTORIES))}"
        )

    logger.debug("Building provider '{}' via registry", provider_lower)
    return factory(
        provider=provider_lower,
        source_lang=source_lang,
        target_lang=target_lang,
        source_lang_display=source_lang_display,
        target_lang_display=target_lang_display,
        capitalize=capitalize,
        max_retries=max_retries,
        model=model,
        chunk_size=chunk_size,
        max_concurrent_chunks=max_concurrent_chunks,
        chunk_token_budget=chunk_token_budget,
        chunk_max_text_length=chunk_max_text_length,
        chunk_mode=chunk_mode,
        glossary=glossary,
    )
