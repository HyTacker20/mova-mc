"""LLM-as-judge QA engine for evaluating and correcting translations.

Provides a ``LlmJudge`` that scores translations via an LLM transport,
and helper types/functions for parsing verdicts and managing re-translation.
"""

from __future__ import annotations

import hashlib
import json
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from typing import Any, Protocol

from loguru import logger

from ...application.batching import chunk_list
from ...application.ports import ProgressSink
from ...utils.cancellation import cancel_token
from ...utils.retry_logic import global_rate_limiter
from .glossary import get_relevant_terms
from .judge_prompts import JUDGE_PROMPT_VERSION, make_judge_prompt
from .openai_like import LLMTransport
from .reasoning_models import strip_thinking_artifacts

# Regex to strip ```json fences
_CODE_FENCE_RE = re.compile(r"^```(?:json)?\s*$", re.MULTILINE)
# Trailing comma before closing brace (common LLM mistake)
_TRAILING_COMMA_RE = re.compile(r",\s*([}\]])")


class VerdictCache(Protocol):
    def get_verdict(self, key: str) -> tuple[str, int | None, str | None, int] | None: ...

    def set_verdict(
        self, key: str, verdict: str, score: int | None = None,
        issue: str | None = None, attempts: int = 0,
    ) -> None: ...

    def get_verdicts(self, keys: list[str]) -> dict[str, tuple[str, int | None, str | None, int]]: ...

    def set_verdicts(
        self, entries: dict[str, tuple[str, int | None, str | None, int]],
    ) -> None: ...


def build_verdict_cache_key(
    source_text: str,
    translated_text: str,
    target_lang: str,
    judge_model: str,
) -> str:
    """Build a deterministic key for the verdict cache."""
    raw = f"{source_text}|{translated_text}|{target_lang}|{judge_model}|{JUDGE_PROMPT_VERSION}"
    return hashlib.sha256(raw.encode()).hexdigest()


@dataclass(frozen=True)
class Verdict:
    """The judgement outcome for a single translation entry."""

    verdict: str  # "ok" | "flag"
    score: int | None = None
    issue: str | None = None
    why: str | None = None
    fix: str | None = None

    @property
    def is_flag(self) -> bool:
        return self.verdict == "flag"


def display_score(verdict: Verdict) -> int:
    """Return a displayable 1..5 score for UI and logs.

    The judge only includes ``score`` for flagged entries; ok verdicts have
    ``score=None``.  Default to 5 for ok and 1 for flag without score.
    """
    if verdict.score is not None:
        return verdict.score
    return 5 if not verdict.is_flag else 1


_MAX_WHY_WORDS = 25


def _normalize_verdict_text(text: str) -> str:
    return " ".join(text.split())


def _default_why(issue: str) -> str:
    _WHY_FALLBACK: dict[str, str] = {
        "russism": "contains Russian words or surzhyk (mixed Russian/Ukrainian)",
        "grammar": "grammatical error (case, gender, or agreement)",
        "meaning": "mistranslation that changes the intended meaning",
        "terminology": "violates Minecraft mod translation terminology",
        "untranslated": "text left in the wrong language",
        "punctuation": "added or removed trailing punctuation",
        "placeholder": "missing or altered placeholder (%s, %d, §-code)",
    }
    return _WHY_FALLBACK.get(issue, f"translation quality issue: {issue}")


def verdict_from_entry(entry: dict[str, Any], tgt: str) -> Verdict:
    """Build a :class:`Verdict` from a parsed judge JSON entry."""
    if entry.get("v") != "flag":
        return Verdict("ok")

    fix = str(entry.get("fix") or "")
    if fix and _normalize_verdict_text(fix) == _normalize_verdict_text(tgt):
        return Verdict("ok")

    issue = entry.get("issue")
    issue_str = str(issue) if issue is not None else None
    why = entry.get("why")
    why_str = str(why).strip() if why else None
    if why_str and len(why_str.split()) > _MAX_WHY_WORDS:
        why_str = _default_why(issue_str or "unknown")

    return Verdict(
        verdict="flag",
        score=entry.get("score"),
        issue=issue_str,
        why=why_str,
        fix=fix or None,
    )


def parse_judge_response(response: str) -> dict[str, dict[str, Any]] | None:
    """Parse the JSON response from the judge LLM.

    Tolerant of:
    - Markdown code fences (`````json ... `````)
    - Leading/trailing text outside the JSON object
    - Trailing commas before closing braces

    Returns ``dict[str, dict]`` on success (one entry per input key),
    or ``None`` if parsing fails entirely.
    """
    text = strip_thinking_artifacts(response.strip())

    # Remove markdown code fences
    text = _CODE_FENCE_RE.sub("", text).strip()

    # Try multiple extraction strategies (reasoning models may prepend text)
    candidates: list[str] = []

    # Strategy 1: first { to last } (standard)
    first_brace = text.find("{")
    last_brace = text.rfind("}")
    if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
        candidates.append(text[first_brace : last_brace + 1])

    # Strategy 2: last { to last } (JSON at end, reasoning before)
    if first_brace != -1 and last_brace != -1:
        last_open = text.rfind("{", 0, last_brace)
        if last_open > first_brace:
            candidates.append(text[last_open : last_brace + 1])

    if not candidates:
        return None

    for candidate in candidates:
        # Handle trailing commas before closing braces/brackets
        candidate = _TRAILING_COMMA_RE.sub(r"\1", candidate)
        try:
            parsed = json.loads(candidate)
            if isinstance(parsed, dict):
                return {str(k): v for k, v in parsed.items() if isinstance(v, dict)}
        except json.JSONDecodeError:
            continue

    logger.debug(
        "parse_judge_response: all strategies failed. "
        "Text (first 200): {!r}",
        text[:200],
    )
    return None


def _verdict_from_cache_row(row: tuple[str, int | None, str | None, int]) -> Verdict:
    verdict_str, score, issue, _attempts = row
    if verdict_str == "flag":
        return Verdict(verdict="flag", score=score, issue=issue)
    return Verdict("ok")


class LlmJudge:
    """LLM-based QA judge for translation quality evaluation.

    Batches entries for efficient review, parses structured verdicts,
    and fails open on transport/parse errors.
    """

    def __init__(
        self,
        transport: LLMTransport,
        source_display: str,
        target_display: str,
        *,
        glossary: dict[str, str] | None = None,
        chunk_size: int = 25,
        max_tokens: int = 2048,
        cache: VerdictCache | None = None,
        target_lang: str = "",
        judge_model: str = "",
        judge_workers: int = 1,
        service_name: str = "judge",
        progress: ProgressSink | None = None,
    ) -> None:
        self._transport = transport
        self._source_display = source_display
        self._target_display = target_display
        self._glossary = glossary or {}
        self._chunk_size = chunk_size
        self._max_tokens = max_tokens
        self._cache = cache
        self._target_lang = target_lang
        self._judge_model = judge_model
        self._judge_workers = max(1, judge_workers)
        self._service_name = service_name
        self._progress = progress

    def judge_batch(self, items: list[tuple[str, str, str]]) -> dict[str, Verdict]:
        """Judge a batch of (key, source_text, translated_text) entries.

        Returns a dict mapping each key to its ``Verdict``.
        On any chunk failure (transport error, parse failure), that chunk's
        keys default to ``Verdict("ok")`` — QA must never block a run.
        """
        if not items:
            return {}

        results: dict[str, Verdict] = {}
        uncached: list[tuple[str, str, str]] = []

        if self._cache is not None and self._target_lang and self._judge_model:
            key_to_vkey = {
                item_key: build_verdict_cache_key(src, tgt, self._target_lang, self._judge_model)
                for item_key, src, tgt in items
            }
            if hasattr(self._cache, "get_verdicts"):
                cached_rows = self._cache.get_verdicts(list(key_to_vkey.values()))
            else:
                cached_rows = {
                    vk: row
                    for vk in key_to_vkey.values()
                    if (row := self._cache.get_verdict(vk)) is not None
                }
            vkey_to_item = {v: k for k, v in key_to_vkey.items()}
            for vkey, row in cached_rows.items():
                item_key = vkey_to_item[vkey]
                results[item_key] = _verdict_from_cache_row(row)
            for item in items:
                if item[0] not in results:
                    uncached.append(item)
        else:
            uncached = list(items)

        if not uncached:
            return results

        all_sources = [src for _, src, _ in uncached]
        glossary_terms = get_relevant_terms(self._glossary, all_sources)
        system_prompt = make_judge_prompt(
            self._source_display,
            self._target_display,
            glossary_terms=glossary_terms,
        )

        chunks = chunk_list(uncached, self._chunk_size)
        workers = min(self._judge_workers, max(1, len(chunks)))

        if workers <= 1:
            for chunk in chunks:
                cancel_token.raise_if_set()
                chunk_results = self._judge_chunk(chunk, system_prompt)
                results.update(chunk_results)
        else:
            with ThreadPoolExecutor(max_workers=workers) as executor:
                future_map = {
                    executor.submit(self._judge_chunk, chunk, system_prompt): chunk
                    for chunk in chunks
                }
                for future in as_completed(future_map):
                    cancel_token.raise_if_set()
                    chunk_results = future.result()
                    results.update(chunk_results)

        return results

    def _store_verdicts(self, chunk: list[tuple[str, str, str]], verdicts: dict[str, Verdict]) -> None:
        if self._cache is None or not self._target_lang or not self._judge_model:
            return
        entries: dict[str, tuple[str, int | None, str | None, int]] = {}
        for key, src, tgt in chunk:
            verdict = verdicts.get(key)
            if verdict is None:
                continue
            vkey = build_verdict_cache_key(src, tgt, self._target_lang, self._judge_model)
            entries[vkey] = (verdict.verdict, verdict.score, verdict.issue, 0)
        if not entries:
            return
        if hasattr(self._cache, "set_verdicts"):
            self._cache.set_verdicts(entries)
        else:
            for vkey, row in entries.items():
                self._cache.set_verdict(vkey, row[0], row[1], row[2], row[3])

    def _judge_chunk(
        self,
        chunk: list[tuple[str, str, str]],
        system_prompt: str,
    ) -> dict[str, Verdict]:
        """Judge a single chunk, returning a key→Verdict mapping.

        On failure, all keys in this chunk default to ``Verdict("ok")``.
        """
        payload: dict[str, dict[str, str]] = {}
        for key, src, tgt in chunk:
            payload[key] = {"src": src, "tgt": tgt}

        chunk_tokens = max(256, min(self._max_tokens, 72 * len(chunk)))

        try:
            global_rate_limiter.apply_service_delay(self._service_name)
            response = self._transport.complete(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
                ],
                temperature=0.0,
                max_tokens=chunk_tokens,
            )
            parsed = parse_judge_response(response)
            if parsed is None:
                logger.warning(
                    "Judge: unparseable response for chunk of {} items, defaulting to ok. "
                    "Raw response (first 300 chars): {!r}",
                    len(chunk),
                    response[:300],
                )
                if self._progress is not None:
                    self._progress.report(
                        "qa_inline_note",
                        key="",
                        message=(
                            f"judge: could not parse response ({len(chunk)} items) "
                            "— batch passed without review"
                        ),
                    )
                fallback: dict[str, Verdict] = {key: Verdict("ok") for key, _, _ in chunk}
                self._store_verdicts(chunk, fallback)
                return fallback

            verdicts: dict[str, Verdict] = {}
            for key, _src, tgt in chunk:
                entry = parsed.get(key, {})
                if isinstance(entry, dict):
                    verdicts[key] = verdict_from_entry(entry, tgt)
                else:
                    verdicts[key] = Verdict("ok")
            self._store_verdicts(chunk, verdicts)
            return verdicts

        except Exception:
            logger.exception("Judge: transport error for chunk of {} items, defaulting to ok", len(chunk))
            return {key: Verdict("ok") for key, _, _ in chunk}
