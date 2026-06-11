"""Unified LLM provider for OpenAI, LiteLLM, and compatible APIs (sync + async)."""

from __future__ import annotations

import asyncio
import json
from typing import Protocol

from loguru import logger

from ...application.batching import chunk_list, parse_chunk_response
from ...domain.models import TranslationResult, TranslationUnit
from ...exceptions import TranslationServiceError
from ...utils.cancellation import cancel_token
from ...utils.retry_logic import create_retry_decorator, global_rate_limiter
from .glossary import get_relevant_terms
from .helpers import capitalize_first
from .judge_prompts import make_feedback_user_prompt
from .prompts import (
    LANG_SPECIFIC_INSTRUCTIONS,
    make_chunk_system_prompt,
    make_system_prompt,
    make_user_prompt,
)


class LLMTransport(Protocol):
    """Protocol for LLM API transports (sync + async)."""

    def complete(self, messages: list[dict[str, str]], temperature: float, max_tokens: int) -> str: ...

    async def acomplete(self, messages: list[dict[str, str]], temperature: float, max_tokens: int) -> str: ...


class OpenAILikeProvider:
    """Unified LLM translation provider for OpenAI, LiteLLM, and compatible APIs.

    Uses a pluggable Transport protocol for the actual API call, allowing the
    same provider class to work with OpenAI SDK, LiteLLM, or custom
    OpenAI-compatible endpoints. Supports single-item translation,
    chunked batch translation with JSON responses, and parallel batch translation
    via ThreadPoolExecutor (sync) or asyncio (async). Rate limiting is applied
    per-call via the global limiter.

    When *source_lang_display* / *target_lang_display* are provided they are used
    in the system prompt in place of the raw language codes so the LLM sees
    human-readable names like "English" / "Ukrainian".
    """

    _CHUNK_SIZE = 25
    _MAX_TOKENS_SINGLE = 1000
    _MAX_TOKENS_CHUNK = 4096
    _MAX_CHUNK_TEXT_LENGTH = 200

    def __init__(
        self,
        source_lang: str,
        target_lang: str,
        transport: LLMTransport,
        service_name: str = "openai",
        capitalize: bool = True,
        max_retries: int = 3,
        chunk_size: int | None = None,
        *,
        source_lang_display: str | None = None,
        target_lang_display: str | None = None,
        glossary: dict[str, str] | None = None,
    ) -> None:
        self.source_lang = source_lang
        self.target_lang = target_lang
        self.source_lang_display = source_lang_display or source_lang
        self.target_lang_display = target_lang_display or target_lang
        self.capitalize = capitalize
        self._transport = transport
        self._service_name = service_name
        self._retry = create_retry_decorator(service_name, max_retries=max_retries)
        if chunk_size is not None:
            self._CHUNK_SIZE = chunk_size

        self._lang_instructions = LANG_SPECIFIC_INSTRUCTIONS.get(self.target_lang, "")
        self._glossary: dict[str, str] = glossary or {}

    _COMMENTARY_PATTERNS = (
        "is very natural",
        "is also understandable",
        "is also natural",
        "let's go with",
        "i'd translate",
        "i would translate",
        "here is the translation",
        "here's the translation",
        "the translation is",
        "translation:",
        "note:",
        "as a translator",
    )

    @staticmethod
    def _looks_like_commentary(response: str, original: str) -> bool:
        """Heuristic: detect when the model wrote commentary instead of a translation."""
        resp_lower = response.lower()
        for pattern in OpenAILikeProvider._COMMENTARY_PATTERNS:
            if pattern in resp_lower:
                return True
        return False

    # ── Prompt helpers ────────────────────────────────────────────────

    def _build_system_prompt(self, glossary_terms: str = "") -> str:
        return make_system_prompt(
            self.source_lang_display,
            self.target_lang_display,
            lang_specific_instructions=self._lang_instructions,
            glossary_terms=glossary_terms,
        )

    def _build_chunk_system_prompt(self, glossary_terms: str = "") -> str:
        return make_chunk_system_prompt(
            self.source_lang_display,
            self.target_lang_display,
            lang_specific_instructions=self._lang_instructions,
            glossary_terms=glossary_terms,
        )

    # ── Sync translate ────────────────────────────────────────────────

    def _translate_text(self, text: str, hint_text: str | None = None) -> str:
        if not text.strip():
            return text

        transport_name = self._transport.__class__.__name__
        src_log = text.replace("\n", "\\n")
        logger.debug(f"[{transport_name}] request: \"{src_log}\"")

        @self._retry
        def _do_translate(t: str, hint: str | None = hint_text) -> str:
            global_rate_limiter.apply_service_delay(self._service_name)
            glossary_terms = get_relevant_terms(self._glossary, [t])
            system_prompt = self._build_system_prompt(glossary_terms)
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": make_user_prompt(t, hint)},
            ]
            result = self._transport.complete(messages, temperature=0.3, max_tokens=self._MAX_TOKENS_SINGLE)
            translated = result.strip()
            if not translated and t.strip():
                raise TranslationServiceError(f"Empty response for: {t[:80]}...")
            # Reject responses that look like commentary/analysis instead of a direct translation
            if self._looks_like_commentary(translated, t):
                logger.warning("Response looks like commentary, not translation — falling back to original")
                raise TranslationServiceError(f"Commentary response for: {t[:80]}...")
            if self.capitalize and translated:
                translated = capitalize_first(translated)
            return translated

        try:
            result = _do_translate(text)
        except TranslationServiceError:
            # Full-text translation failed — try splitting by paragraphs
            # Handle both real newlines and literal \n escape sequences
            # (the latter come from .lang files which use \n instead of real newlines)
            _LITERAL_NL = "\\n"
            if "\n\n" in text:
                sep = "\n\n"
            elif _LITERAL_NL * 2 in text:
                sep = _LITERAL_NL * 2
            else:
                raise

            logger.warning(
                "Full-text translation failed, splitting by paragraphs for: {}...", text[:60]
            )
            paragraphs = [p.strip() for p in text.split(sep) if p.strip()]
            translated_parts: list[str] = []
            for para in paragraphs:
                try:
                    translated_parts.append(_do_translate(para))
                except TranslationServiceError:
                    translated_parts.append(para)  # keep original on failure
            result = sep.join(translated_parts)

        tgt_log = result.replace("\n", "\\n")
        logger.debug(f"[{transport_name}] response: \"{tgt_log}\"")
        return result  # type: ignore[no-any-return]

    def translate(self, text: str) -> str:
        try:
            return self._translate_text(text)
        except Exception as e:
            raise TranslationServiceError("OpenAI-like translation failed") from e

    def translate_unit(self, unit: TranslationUnit) -> TranslationResult:
        try:
            translated_text = self._translate_text(unit.source_text, unit.hint_text)
        except Exception as exc:
            logger.exception(f"Translation failed for '{unit.key}'")
            return TranslationResult(
                unit=unit,
                translated_text=unit.source_text,
                success=False,
                error=str(exc),
            )
        return TranslationResult(unit=unit, translated_text=translated_text, success=True)

    def retranslate_with_feedback(
        self,
        source_text: str,
        prev_tgt: str,
        issue: str,
        why: str,
    ) -> str:
        """Re-translate one entry using the feedback user-prompt.

        Uses the standard target-language system prompt and a user prompt
        that explains why the previous translation was rejected.

        Raises ``TranslationServiceError`` on empty response.
        """
        if not source_text.strip():
            return source_text

        glossary_terms = get_relevant_terms(self._glossary, [source_text, prev_tgt])
        system_prompt = self._build_system_prompt(glossary_terms)
        user_prompt = make_feedback_user_prompt(
            source_lang=self.source_lang_display,
            target_lang=self.target_lang_display,
            src=source_text,
            prev_tgt=prev_tgt,
            issue=issue,
            why=why,
        )

        @self._retry
        def _do_retranslate() -> str:
            global_rate_limiter.apply_service_delay(self._service_name)
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ]
            result = self._transport.complete(messages, temperature=0.3, max_tokens=self._MAX_TOKENS_SINGLE)
            translated = result.strip()
            if not translated:
                raise TranslationServiceError(f"Empty re-translation response for: {source_text[:80]}...")
            if self.capitalize:
                translated = capitalize_first(translated)
            return translated

        try:
            return _do_retranslate()  # type: ignore[no-any-return]
        except TranslationServiceError:
            logger.warning("Re-translation with feedback failed for: {}...", source_text[:60])
            raise

    def _translate_chunk(
        self,
        chunk: list[tuple[str, str]],
        hints: dict[str, str | None] | None = None,
    ) -> dict[str, str]:
        if not chunk:
            return {}
        if len(chunk) == 1:
            key, text = chunk[0]
            hint = hints.get(key) if hints else None
            try:
                return {key: self._translate_text(text, hint)}
            except Exception:
                return {key: text}

        items = {key: text for key, text in chunk}
        payload = json.dumps(items, ensure_ascii=False)

        @self._retry
        def _do_translate(p: str) -> str:
            global_rate_limiter.apply_service_delay(self._service_name)
            glossary_terms = get_relevant_terms(self._glossary, list(items.values()))
            system_prompt = self._build_chunk_system_prompt(glossary_terms)
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": p},
            ]
            return self._transport.complete(messages, temperature=0.3, max_tokens=self._MAX_TOKENS_CHUNK)

        try:
            cancel_token.raise_if_set()
            response = _do_translate(payload)
            cancel_token.raise_if_set()
            result = parse_chunk_response(response)
            if result is not None:
                if self.capitalize:
                    result = {k: capitalize_first(v) if isinstance(v, str) and v else v for k, v in result.items()}
                result = {k: v for k, v in result.items() if v}
                for key in items:
                    if key not in result:
                        result[key] = items[key]
                return result
            logger.warning("Chunk response parse failed, falling back to per-item translation")
            result = {}
            for key, text in chunk:
                hint = hints.get(key) if hints else None
                try:
                    result[key] = self._translate_text(text, hint)
                except Exception:
                    logger.exception(f"Fallback per-item translation failed for key '{key}'")
                    result[key] = text
            return result
        except Exception:
            logger.exception(f"Chunk translation failed for {len(chunk)} items")
            return {key: text for key, text in chunk}

    # ── New-style sync batch ──────────────────────────────────────────

    def translate_batch(self, units: list[TranslationUnit]) -> list[TranslationResult]:
        results: list[TranslationResult] = []
        for unit in units:
            try:
                translated = self._translate_text(unit.source_text, unit.hint_text)
                results.append(TranslationResult(unit=unit, translated_text=translated, success=True))
            except Exception as exc:
                results.append(
                    TranslationResult(unit=unit, translated_text=unit.source_text, success=False, error=str(exc))
                )
        return results

    # ── Async translate ───────────────────────────────────────────────

    async def _translate_text_async(self, text: str, hint_text: str | None = None) -> str:
        if not text.strip():
            return text

        @self._retry
        async def _do_translate(t: str, hint: str | None = hint_text) -> str:
            global_rate_limiter.apply_service_delay(self._service_name)
            glossary_terms = get_relevant_terms(self._glossary, [t])
            system_prompt = self._build_system_prompt(glossary_terms)
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": make_user_prompt(t, hint)},
            ]
            result = await self._transport.acomplete(messages, temperature=0.3, max_tokens=self._MAX_TOKENS_SINGLE)
            translated = result.strip()
            if not translated and t.strip():
                raise TranslationServiceError(f"Empty response for: {t[:80]}...")
            if self.capitalize and translated:
                translated = capitalize_first(translated)
            return translated

        return await _do_translate(text)  # type: ignore[no-any-return]

    async def translate_async(self, text: str) -> str:
        try:
            return await self._translate_text_async(text)
        except Exception as e:
            raise TranslationServiceError("OpenAI-like translation failed") from e

    async def translate_unit_async(self, unit: TranslationUnit) -> TranslationResult:
        try:
            translated_text = await self._translate_text_async(unit.source_text, unit.hint_text)
        except Exception as exc:
            logger.exception(f"Async translation failed for '{unit.key}'")
            return TranslationResult(
                unit=unit,
                translated_text=unit.source_text,
                success=False,
                error=str(exc),
            )
        return TranslationResult(unit=unit, translated_text=translated_text, success=True)

    async def _translate_chunk_async(self, chunk: list[tuple[str, str]]) -> dict[str, str]:
        if not chunk:
            return {}
        if len(chunk) == 1:
            key, text = chunk[0]
            try:
                return {key: await self.translate_async(text)}
            except Exception:
                return {key: text}

        items = {key: text for key, text in chunk}

        @self._retry
        async def _do_translate(p: str) -> str:
            global_rate_limiter.apply_service_delay(self._service_name)
            glossary_terms = get_relevant_terms(self._glossary, list(items.values()))
            system_prompt = self._build_chunk_system_prompt(glossary_terms)
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": p},
            ]
            return await self._transport.acomplete(messages, temperature=0.3, max_tokens=self._MAX_TOKENS_CHUNK)

        try:
            payload = json.dumps(items, ensure_ascii=False)
            response = await _do_translate(payload)
            result = parse_chunk_response(response)
            if result is not None:
                if self.capitalize:
                    result = {k: capitalize_first(v) if isinstance(v, str) and v else v for k, v in result.items()}
                result = {k: v for k, v in result.items() if v}
                for key in items:
                    if key not in result:
                        result[key] = items[key]
                return result
            logger.warning("Async chunk response parse failed, falling back to per-item")
            result = {}
            for key, text in chunk:
                try:
                    result[key] = await self.translate_async(text)
                except Exception:
                    result[key] = text
            return result
        except Exception:
            logger.exception(f"Async chunk translation failed for {len(chunk)} items")
            return {key: text for key, text in chunk}

    async def translate_batch_async(self, units: list[TranslationUnit]) -> list[TranslationResult]:
        """Async batch translation with structured results.

        Processes items concurrently using asyncio.gather.
        Short texts are batched into chunks; long texts go individually.
        """
        items = [(unit.key, unit.source_text, unit) for unit in units]
        short_items = [(k, t, u) for k, t, u in items if len(t) <= self._MAX_CHUNK_TEXT_LENGTH]
        long_items = [(k, t, u) for k, t, u in items if len(t) > self._MAX_CHUNK_TEXT_LENGTH]

        results: dict[str, TranslationResult] = {}

        # Long items individually
        for key, text, unit in long_items:
            try:
                translated = await self._translate_text_async(text)
                results[key] = TranslationResult(unit=unit, translated_text=translated, success=True)
            except Exception as exc:
                results[key] = TranslationResult(unit=unit, translated_text=text, success=False, error=str(exc))

        # Short items in parallel chunks
        if short_items:
            chunk_size = self._CHUNK_SIZE
            chunks_raw = chunk_list([(k, t) for k, t, _ in short_items], chunk_size)
            unit_map = {unit.key: unit for _, _, unit in short_items}

            async def _process_chunk(chunk: list[tuple[str, str]]) -> None:
                chunk_result = await self._translate_chunk_async(chunk)
                for key, text in chunk:
                    unit = unit_map[key]
                    if key in chunk_result:
                        results[key] = TranslationResult(unit=unit, translated_text=chunk_result[key], success=True)
                    else:
                        results[key] = TranslationResult(unit=unit, translated_text=text, success=False)

            await asyncio.gather(*[_process_chunk(c) for c in chunks_raw], return_exceptions=True)

        return [
            results.get(u.key, TranslationResult(unit=u, translated_text=u.source_text, success=False))
            for u in units
        ]
