from __future__ import annotations

import hashlib
from collections.abc import Callable

from loguru import logger

from ...application.ports import TranslationCache, TranslationProvider
from ...domain.models import TranslationResult, TranslationUnit


class CachingProvider:
    """A caching decorator around a ``TranslationProvider``.

    The cache key incorporates the provider name, model, prompt version,
    and (optionally) a glossary hash so that switching providers or
    updating prompts invalidates old entries.
    """

    def __init__(
        self,
        inner: TranslationProvider,
        cache: TranslationCache,
        source_lang: str,
        target_lang: str,
        *,
        provider_name: str = "",
        model: str = "",
        prompt_version: str = "",
        glossary_signature: str = "",
        no_cache: bool = False,
    ) -> None:
        self._inner = inner
        self._cache = cache
        self._source_lang = source_lang
        self._target_lang = target_lang
        self._provider_name = provider_name
        self._model = model
        self._prompt_version = prompt_version
        self._glossary_signature = glossary_signature
        self._no_cache = no_cache

    def _cache_key(self, text: str) -> str:
        raw = (
            f"{text}|{self._source_lang}|{self._target_lang}"
            f"|{self._provider_name}|{self._model}|{self._prompt_version}"
            f"|{self._glossary_signature}"
        )
        return hashlib.sha256(raw.encode()).hexdigest()

    def translate(self, text: str) -> str:
        key = self._cache_key(text)
        cached = self._cache.get(key)
        if cached is not None:
            preview = text[:60] + "..." if len(text) > 60 else text
            logger.debug(f'[cache] HIT for "{preview}"')
            return cached

        preview = text[:60] + "..." if len(text) > 60 else text
        logger.debug(f'[cache] MISS for "{preview}"')
        result = self._inner.translate(text)
        if result:
            self._cache.set(key, result)
        return result

    def translate_unit(self, unit: TranslationUnit) -> TranslationResult:
        key = self._cache_key(unit.source_text)
        cached = self._cache.get(key)
        if cached is not None:
            preview = unit.source_text[:60] + "..." if len(unit.source_text) > 60 else unit.source_text
            logger.debug(f"[cache] HIT for key '{unit.key}': \"{preview}\"")
            return TranslationResult(unit=unit, translated_text=cached, success=True, cached=True)

        preview = unit.source_text[:60] + "..." if len(unit.source_text) > 60 else unit.source_text
        logger.debug(f"[cache] MISS for key '{unit.key}': \"{preview}\"")
        result = self._inner.translate_unit(unit)
        if result.success and result.translated_text:
            self._cache.set(key, result.translated_text)
        return result

    def translate_batch(self, units: list[TranslationUnit]) -> list[TranslationResult]:
        results: list[TranslationResult | None] = [None] * len(units)
        uncached_indices: list[int] = []
        uncached_units: list[TranslationUnit] = []

        for i, unit in enumerate(units):
            key = self._cache_key(unit.source_text)
            cached = self._cache.get(key)
            if cached is not None:
                results[i] = TranslationResult(unit=unit, translated_text=cached, success=True, cached=True)
            else:
                uncached_indices.append(i)
                uncached_units.append(unit)

        cached_count = len(units) - len(uncached_units)
        if cached_count > 0:
            logger.info(
                "[cache] {} / {} entries served from cache",
                cached_count,
                len(units),
            )

        if uncached_units:
            for idx, unit in zip(uncached_indices, uncached_units, strict=True):
                result = self._inner.translate_unit(unit)
                if result.success and result.translated_text:
                    self._cache.set(self._cache_key(result.unit.source_text), result.translated_text)
                results[idx] = result

        return [r for r in results if r is not None]

    def __getattr__(self, name: str):
        return getattr(self._inner, name)

    def recache(self, source_text: str, corrected_text: str) -> None:
        """Overwrite the cached translation for *source_text*.

        Uses the same ``_cache_key`` so future runs return the corrected text.
        No-op when ``no_cache`` is set.
        """
        if self._no_cache:
            return
        key = self._cache_key(source_text)
        self._cache.set(key, corrected_text)
        preview = source_text[:60] + "..." if len(source_text) > 60 else source_text
        logger.debug(f'[cache] RECACHE for "{preview}": "{corrected_text[:60]}..."')

    # ── Async methods ───────────────────────────────────────────────

    async def translate_async(self, text: str) -> str:
        key = self._cache_key(text)
        cached = self._cache.get(key)
        if cached is not None:
            return cached
        result = await self._inner.translate_async(text)
        if result:
            self._cache.set(key, result)
        return result

    async def translate_unit_async(self, unit: TranslationUnit) -> TranslationResult:
        key = self._cache_key(unit.source_text)
        cached = self._cache.get(key)
        if cached is not None:
            return TranslationResult(unit=unit, translated_text=cached, success=True, cached=True)
        result = await self._inner.translate_unit_async(unit)
        if result.success and result.translated_text:
            self._cache.set(key, result.translated_text)
        return result

    async def translate_batch_async(
        self,
        units: list[TranslationUnit],
        *,
        on_entry: Callable[[str, str, str], None] | None = None,
    ) -> list[TranslationResult]:
        entry_cb = on_entry
        results: list[TranslationResult | None] = [None] * len(units)
        uncached_indices: list[int] = []
        uncached_units: list[TranslationUnit] = []

        for i, unit in enumerate(units):
            key = self._cache_key(unit.source_text)
            cached = self._cache.get(key)
            if cached is not None:
                results[i] = TranslationResult(unit=unit, translated_text=cached, success=True, cached=True)
                if entry_cb is not None:
                    entry_cb(unit.key, unit.source_text, cached)
            else:
                uncached_indices.append(i)
                uncached_units.append(unit)

        cached_count = len(units) - len(uncached_units)
        if cached_count > 0:
            logger.info(
                "[cache] {} / {} entries served from cache",
                cached_count,
                len(units),
            )

        if uncached_units:
            new_results = await self._inner.translate_batch_async(uncached_units, on_entry=entry_cb)
            for idx, r in zip(uncached_indices, new_results, strict=True):
                if r.success and r.translated_text:
                    self._cache.set(self._cache_key(r.unit.source_text), r.translated_text)
                results[idx] = r

        return [r for r in results if r is not None]
