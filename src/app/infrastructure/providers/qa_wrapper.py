"""Inline QA wrapper — per-item streaming QA during batch translation.

Wraps a ``TranslationProvider`` so that each translated item is judged by the
LLM judge on a **background thread** without blocking the translation pipeline.
Flagged items are corrected in-place (judge's ``fix`` field or re-translation
with feedback) as soon as the QA worker finishes processing them.

QA operations are batched (``chunk_size`` items per API call) to reduce latency
while keeping the translate workers busy at all times.
"""

from __future__ import annotations

import queue
import re
import threading
import time
from dataclasses import replace
from typing import Any

from loguru import logger

from ...application.ports import ProgressSink, TranslationProvider
from ...domain.models import TranslationResult, TranslationUnit
from ...domain.placeholders import validate_placeholders
from ...utils.cancellation import cancel_token
from .judge import LlmJudge, Verdict, display_score

_IDLE_FLUSH_SECONDS = 1.5

# Russian-only Cyrillic letters that do NOT exist in Ukrainian.
# Used as a fast deterministic sanity check for ru→uk judge fixes.
_RUSSIAN_ONLY_LETTERS_RE = re.compile(r"[ёъыэЁЪЫЭ]")

# ── Sanity checks for Tier-1 fix acceptance ───────────────────────────
# Tier 1 accepts fixes that (a) pass lint AND (b) pass structural sanity.
# Fixes that fail either check go to Tier 2 (re-judge).

def _is_safe_fix(original_translation: str, fix: str) -> bool:
    """Return True if *fix* is a structurally safe edit of *original_translation*.

    Guards against judge fixes that:
    - Truncate text (drop sentences/paragraphs)
    - Replace correct terminology wholesale
    - Change the text structure drastically

    These are heuristic checks — the intent is to catch *obviously wrong*
    fixes before they bypass re-judge.  The thresholds are deliberately
    loose to avoid blocking valid corrections.
    """
    if not fix or not original_translation:
        return False

    # ── Length guard: fix must not be drastically shorter ──
    # Catches truncation (e.g. judge drops the first sentence of a tooltip).
    orig_len = len(original_translation)
    fix_len = len(fix)
    if fix_len < orig_len * 0.4:
        return False

    # ── Word-count guard: fix must not have radically different granularity ──
    # Catches replacement of a multi-word phrase with a single unrelated word
    # (e.g. "Крем'яний паксел" → "Крем'яна лопата" — this would pass length
    # check, but we want the judge to *re-think* such changes).
    orig_words = len(original_translation.split())
    fix_words = len(fix.split())
    if orig_words > 1 and fix_words > 1:
        if fix_words < orig_words * 0.5 or fix_words > orig_words * 2.0:
            return False

    return True

QaMeta = tuple[int | None, str | None, int]


def _normalize_trailing_period(source: str, translated: str) -> str:
    """Strip trailing period from *translated* if *source* does not have one.

    Minecraft lang values are UI labels that rarely end with a full stop.
    LLMs often add one; this heuristic undoes that before the text reaches
    the judge or the output file.
    """
    src_stripped = source.rstrip()
    tgt_stripped = translated.rstrip()
    if src_stripped and tgt_stripped:
        if not src_stripped.endswith(".") and tgt_stripped.endswith("."):
            return tgt_stripped.rstrip(".").rstrip()
    return translated


class InlineQaWrapper:
    """Wraps a ``TranslationProvider`` with background per-item QA.

    Flow
    ----
    1. ``batch_translate`` submits items to the inner provider.
    2. Each finished translation is **immediately** forwarded to the caller
       (``on_entry`` fires with the raw text — no blocking).
    3. A background worker pulls items from a queue, judges them in batches
       (configurable ``chunk_size``), and corrects flagged entries.
    4. Corrections are logged and applied to the final result dict.

    From the caller's perspective, translation finishes at full speed; QA
    results arrive moments later as corrections.
    """

    def __init__(
        self,
        inner: TranslationProvider,
        judge: LlmJudge,
        *,
        corrector: Any | None = None,
        threshold: int = 3,
        max_attempts: int = 2,
        chunk_size: int = 5,
        progress: ProgressSink | None = None,
    ) -> None:
        self._inner = inner
        self._judge = judge
        self._corrector = corrector
        self._threshold = threshold
        self._max_attempts = max_attempts
        self._chunk_size = chunk_size
        self._progress = progress
        self._qa_queued = 0
        self._qa_judged = 0
        self._qa_metadata: dict[str, QaMeta] = {}
        self._qa_metadata_lock = threading.Lock()

        # Ensure the judge batches at most chunk_size items per call
        if self._judge._chunk_size != chunk_size:
            object.__setattr__(self._judge, "_chunk_size", chunk_size)

    def consume_qa_metadata(self) -> dict[str, QaMeta]:
        """Return and clear QA metadata collected during the last batch."""
        with self._qa_metadata_lock:
            meta = dict(self._qa_metadata)
            self._qa_metadata.clear()
            return meta

    def _store_qa_meta(self, key: str, score: int | None, issue: str | None, attempts: int) -> None:
        with self._qa_metadata_lock:
            self._qa_metadata[key] = (score, issue, attempts)

    def _attempt_corrections(
        self,
        key: str,
        source: str,
        translated: str,
        verdict: Verdict,
        *,
        re_judge: bool = True,
    ) -> tuple[str | None, int]:
        """Try to correct a flagged translation up to ``max_attempts`` times."""
        attempts = 0

        if verdict.fix and verdict.fix.strip() and validate_placeholders(source, verdict.fix):
            fix = verdict.fix.strip()
            if _is_safe_fix(translated, fix):
                logger.debug("Inline QA: accepted safe judge fix for {!r}…", source[:60])
                return fix, 0
            logger.debug("Inline QA: re-judging judge fix for {!r}…", source[:60])
            if re_judge:
                try:
                    re_verdicts = self._judge.judge_batch([(f"re:{key}", source, fix)])
                    re_v = re_verdicts.get(f"re:{key}")
                    if re_v is not None and not re_v.is_flag:
                        return fix, 0
                except Exception as exc:
                    logger.warning("Inline QA: single re-judge failed, accepting fix anyway: {}", exc)
                    return fix, 0
                return None, 0
            return fix, 0

        if self._corrector is not None and hasattr(
            self._corrector, "retranslate_with_feedback"
        ):
            prev_tgt = translated
            while attempts < self._max_attempts:
                attempts += 1
                try:
                    corrected = self._corrector.retranslate_with_feedback(
                        source_text=source,
                        prev_tgt=prev_tgt,
                        issue=verdict.issue or "unknown",
                        why=verdict.why or "",
                    )
                except Exception as exc:
                    logger.warning("Inline QA: corrector attempt {}/{} failed: {}", attempts, self._max_attempts, exc)
                    if self._progress is not None:
                        self._progress.report(
                            "qa_correction",
                            key=key,
                            accepted=False,
                            attempt=attempts,
                            max_attempts=self._max_attempts,
                        )
                    continue

                if (
                    not corrected.strip()
                    or corrected.strip() == prev_tgt.strip()
                    or not validate_placeholders(source, corrected)
                ):
                    if self._progress is not None:
                        self._progress.report(
                            "qa_correction",
                            key=key,
                            accepted=False,
                            attempt=attempts,
                            max_attempts=self._max_attempts,
                        )
                    continue

                if not re_judge:
                    return corrected.strip(), attempts

                try:
                    re_verdicts = self._judge.judge_batch(
                        [(f"re:{key}", source, corrected.strip())]
                    )
                    re_v = re_verdicts.get(f"re:{key}")
                    if re_v is not None and not re_v.is_flag:
                        if self._progress is not None:
                            self._progress.report(
                                "qa_correction",
                                key=key,
                                accepted=True,
                                attempt=attempts,
                                max_attempts=self._max_attempts,
                            )
                        return corrected.strip(), attempts
                except Exception as exc:
                    logger.warning("Inline QA: post-correction re-judge failed, accepting correction: {}", exc)
                    if self._progress is not None:
                        self._progress.report(
                            "qa_correction",
                            key=key,
                            accepted=True,
                            attempt=attempts,
                            max_attempts=self._max_attempts,
                        )
                    return corrected.strip(), attempts

                if self._progress is not None:
                    self._progress.report(
                        "qa_correction",
                        key=key,
                        accepted=False,
                        attempt=attempts,
                        max_attempts=self._max_attempts,
                    )

        return None, attempts

    def _needs_correction(self, verdict: Verdict) -> bool:
        return verdict.is_flag and not (
            verdict.score is not None and verdict.score > self._threshold
        )

    def _process_batch(
        self,
        batch: list[tuple[str, str, str]],
        corrections: dict[str, str],
        corrections_lock: threading.Lock,
    ) -> None:
        if not batch:
            return

        t0 = time.monotonic()
        flagged_count = 0
        corrected_count = 0

        if self._progress is not None:
            self._progress.report(
                "qa_inline_judging",
                count=len(batch),
                chunk_size=self._chunk_size,
            )

        try:
            verdicts = self._judge.judge_batch(batch)
        except Exception as exc:
            logger.warning("Inline QA: judge batch failed: {}", exc)
            if self._progress is not None:
                self._progress.report(
                    "qa_inline_error",
                    message=str(exc),
                    elapsed=time.monotonic() - t0,
                )
            return

        for key, source, translated in batch:
            verdict = verdicts.get(key, Verdict("ok"))
            score = display_score(verdict)

            if not self._needs_correction(verdict):
                if verdict.is_flag:
                    self._store_qa_meta(key, verdict.score, verdict.issue, 0)
                continue

            flagged_count += 1
            if self._progress is not None:
                self._progress.report(
                    "qa_verdict",
                    key=key,
                    score=score,
                    is_flagged=True,
                    issue=verdict.issue,
                )

            corrected, attempts = self._attempt_corrections(key, source, translated, verdict)
            if corrected:
                corrected_count += 1
                normalized = _normalize_trailing_period(source, corrected)
                with corrections_lock:
                    corrections[key] = normalized
                self._store_qa_meta(key, score, verdict.issue, attempts)
                if self._progress is not None:
                    self._progress.report(
                        "qa_inline_fix",
                        key=key,
                        original=translated,
                        fixed=normalized,
                    )
            else:
                self._store_qa_meta(key, score, verdict.issue, attempts)

        self._qa_judged += len(batch)
        if self._progress is not None:
            self._progress.report_qa_progress(self._qa_judged, self._qa_queued)
            self._progress.report(
                "qa_inline_summary",
                flagged=flagged_count,
                total=len(batch),
                corrected=corrected_count,
                elapsed=time.monotonic() - t0,
            )

    def _qa_worker_loop(
        self,
        work_queue: queue.Queue[tuple[str, str, str] | None],
        corrections: dict[str, str],
        corrections_lock: threading.Lock,
    ) -> None:
        buffer: list[tuple[str, str, str]] = []
        last_put = time.monotonic()

        while True:
            if cancel_token.is_set():
                while True:
                    try:
                        item = work_queue.get_nowait()
                    except queue.Empty:
                        break
                    if item is not None:
                        buffer.append(item)
                if buffer:
                    self._process_batch(buffer, corrections, corrections_lock)
                return

            try:
                item = work_queue.get(timeout=0.25)
            except queue.Empty:
                if buffer and (time.monotonic() - last_put) >= _IDLE_FLUSH_SECONDS:
                    self._process_batch(buffer, corrections, corrections_lock)
                    buffer = []
                continue

            if item is None:
                if buffer:
                    self._process_batch(buffer, corrections, corrections_lock)
                return

            buffer.append(item)
            last_put = time.monotonic()
            if len(buffer) >= self._chunk_size:
                self._process_batch(buffer, corrections, corrections_lock)
                buffer = []

    def translate(self, text: str) -> str:
        return self._inner.translate(text)

    def translate_unit(self, unit: TranslationUnit) -> TranslationResult:
        return self._inner.translate_unit(unit)

    def translate_batch(
        self, units: list[TranslationUnit]
    ) -> list[TranslationResult]:
        return self._inner.translate_batch(units)

    async def translate_async(self, text: str) -> str:
        return await self._inner.translate_async(text)

    async def translate_unit_async(
        self, unit: TranslationUnit
    ) -> TranslationResult:
        return await self._inner.translate_unit_async(unit)

    async def translate_batch_async(
        self,
        units: list[TranslationUnit],
        *,
        on_entry: object | None = None,
    ) -> list[TranslationResult]:
        if not units:
            return []

        user_on_entry = on_entry if callable(on_entry) else None
        work_queue: queue.Queue[tuple[str, str, str] | None] = queue.Queue()
        corrections: dict[str, str] = {}
        corrections_lock = threading.Lock()

        def wrapped_on_entry(key: str, source: str, translated: str) -> None:
            if user_on_entry is not None:
                user_on_entry(key, source, translated)  # type: ignore[misc]
            tgt = _normalize_trailing_period(source, translated).strip()
            src = source.strip()
            if tgt and tgt != src:
                self._qa_queued += 1
                if self._progress is not None:
                    self._progress.report_qa_progress(self._qa_judged, self._qa_queued)
                work_queue.put((key, source, tgt))

        worker = threading.Thread(
            target=self._qa_worker_loop,
            args=(work_queue, corrections, corrections_lock),
            name="inline-qa",
            daemon=True,
        )
        worker.start()

        try:
            results = await self._inner.translate_batch_async(
                units,
                on_entry=wrapped_on_entry,
            )
        finally:
            work_queue.put(None)
            worker.join()

        out: list[TranslationResult] = []
        for tr in results:
            with corrections_lock:
                new_text = corrections.get(tr.unit.key)
            if new_text and tr.success:
                out.append(replace(tr, translated_text=new_text))
            else:
                out.append(tr)
        return out

    def __getattr__(self, name: str) -> Any:
        return getattr(self._inner, name)
