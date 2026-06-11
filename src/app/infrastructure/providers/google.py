from __future__ import annotations

import asyncio
from collections.abc import Callable

from deep_translator import GoogleTranslator
from loguru import logger

from ...domain.models import TranslationResult, TranslationUnit
from ...exceptions import TranslationServiceError
from ...utils.cancellation import cancel_token
from ...utils.retry_logic import create_retry_decorator, global_rate_limiter
from .helpers import capitalize_first


class GoogleProvider:
    """Translation provider using Google Translate via deep-translator.

    Supports single-item translation. Rate limiting is applied per API call
    through the global rate limiter. The underlying GoogleTranslator is
    stateless, so concurrent calls are safe.
    """

    _CHUNK_SIZE = 0

    def __init__(
        self,
        source_lang: str,
        target_lang: str,
        capitalize: bool = True,
        max_retries: int = 3,
        max_concurrent_chunks: int = 4,
    ) -> None:
        self.source_lang = source_lang
        self.target_lang = target_lang
        self.capitalize = capitalize
        self._max_concurrent_chunks = max(1, max_concurrent_chunks)
        self._retry = create_retry_decorator("google", max_retries=max_retries)
        self._translator = GoogleTranslator(source=self.source_lang, target=self.target_lang)

    def _translate_text(self, text: str) -> str:
        if not text.strip():
            return text

        src_preview = text[:80] + "..." if len(text) > 80 else text
        logger.debug(f"[Google Translate] request: \"{src_preview}\"")

        @self._retry
        def _do_translate(t: str) -> str:
            global_rate_limiter.apply_service_delay("google")
            result = self._translator.translate(t)
            if self.capitalize and result:
                result = capitalize_first(result)
            return result  # type: ignore[no-any-return]

        result = _do_translate(text)  # type: ignore[no-any-return]
        tgt_preview = result[:80] + "..." if result and len(result) > 80 else result
        logger.debug(f"[Google Translate] response: \"{tgt_preview}\"")
        return result  # type: ignore[no-any-return]

    def translate(self, text: str) -> str:
        try:
            return self._translate_text(text)
        except Exception as e:
            raise TranslationServiceError("Google translation failed") from e

    def translate_unit(self, unit: TranslationUnit) -> TranslationResult:
        try:
            translated_text = self._translate_text(unit.source_text)
        except Exception as exc:
            logger.exception(f"Google translation failed for '{unit.key}'")
            return TranslationResult(
                unit=unit,
                translated_text=unit.source_text,
                success=False,
                error=str(exc),
            )

        return TranslationResult(unit=unit, translated_text=translated_text, success=True)

    # ── Async translate (wraps sync in executor) ─────────────────────

    async def translate_async(self, text: str) -> str:
        """Async single-text translation via executor thread."""
        return await asyncio.to_thread(self.translate, text)

    async def translate_unit_async(self, unit: TranslationUnit) -> TranslationResult:
        """Async TranslationUnit translation via executor thread."""
        return await asyncio.to_thread(self.translate_unit, unit)

    async def translate_batch_async(
        self,
        units: list[TranslationUnit],
        *,
        on_entry: Callable[[str, str, str], None] | None = None,
    ) -> list[TranslationResult]:
        """Async batch translation with parallel workers."""
        cancel_token.raise_if_set()
        if not units:
            return []

        sem = asyncio.Semaphore(self._max_concurrent_chunks)
        results: list[TranslationResult | None] = [None] * len(units)

        async def _translate_indexed(index: int, unit: TranslationUnit) -> None:
            async with sem:
                cancel_token.raise_if_set()
                tr = await self.translate_unit_async(unit)
                results[index] = tr
                if on_entry is not None:
                    txt = tr.translated_text if tr.success else unit.source_text
                    on_entry(unit.key, unit.source_text, txt)

        await asyncio.gather(
            *[_translate_indexed(i, unit) for i, unit in enumerate(units)],
            return_exceptions=True,
        )

        return [
            r if r is not None else TranslationResult(unit=u, translated_text=u.source_text, success=False)
            for u, r in zip(units, results, strict=True)
        ]

    # ── New-style sync batch ─────────────────────────────────────────

    def translate_batch(self, units: list[TranslationUnit]) -> list[TranslationResult]:
        results: list[TranslationResult] = []
        for unit in units:
            try:
                translated = self.translate(unit.source_text)
                results.append(TranslationResult(unit=unit, translated_text=translated, success=True))
            except Exception as exc:
                results.append(
                    TranslationResult(unit=unit, translated_text=unit.source_text, success=False, error=str(exc))
                )
        return results
