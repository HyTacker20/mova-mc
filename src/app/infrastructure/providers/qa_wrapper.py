"""Inline QA wrapper — per-item streaming QA during batch translation.

Wraps a ``TranslationProvider`` so that each translated item is judged by the
LLM judge on a **background thread** without blocking the translation pipeline.
Flagged items are corrected in-place (judge's ``fix`` field or re-translation
with feedback) as soon as the QA worker finishes processing them.

QA operations are batched (``chunk_size`` items per API call) to reduce latency
while keeping the translate workers busy at all times.
"""

from __future__ import annotations

import asyncio
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
from ...domain.qa_display import format_provider_model
from ...utils.cancellation import cancel_token
from .judge import LlmJudge, Verdict, display_score

_IDLE_FLUSH_SECONDS = 1.5
_INLINE_QA_STATUS_EMITTED = False

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


def _lint_gate_accept(corrected: str, original: str, target_lang: str) -> bool:
    """Accept a correction that passes deterministic lint when the original failed.

    For ru→uk translations: if *original* contains Russian-only letters (ы, ё, ъ, э)
    and *corrected* does not, the fix is objectively better — skip re-judge.

    Returns ``False`` for any language pair without a lint gate.
    """
    if target_lang != "uk_UA":
        return False
    corrected_has = bool(_RUSSIAN_ONLY_LETTERS_RE.search(corrected))
    original_has = bool(_RUSSIAN_ONLY_LETTERS_RE.search(original))
    return original_has and not corrected_has


def _default_why(issue: str) -> str:
    """Return a default explanation when the judge provides none.

    The corrector's feedback prompt needs a *why* to produce a useful
    re-translation.  When the judge model omits the explanation, this
    fallback gives the corrector enough context to act.
    """
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

        # Per-run accumulators for lifecycle events
        self._run_flagged = 0
        self._run_corrected = 0

        # Emit inline QA active status once per process
        global _INLINE_QA_STATUS_EMITTED
        if self._progress is not None and not _INLINE_QA_STATUS_EMITTED:
            _INLINE_QA_STATUS_EMITTED = True
            judge_model = getattr(self._judge, "_judge_model", "") or "default"
            transport = getattr(self._judge, "_transport", None)
            judge_provider = ""
            if transport is not None:
                judge_provider = getattr(transport, "provider_name", "") or ""
            label = format_provider_model(judge_provider, judge_model)
            self._progress.report(
                "qa_inline_status",
                message=f"Inline QA · {label}",
                provider=judge_provider,
                model=judge_model,
            )

        # Ensure the judge batches at most chunk_size items per call
        if self._judge._chunk_size != chunk_size:
            object.__setattr__(self._judge, "_chunk_size", chunk_size)

    def consume_qa_metadata(self) -> dict[str, QaMeta]:
        """Return and clear QA metadata collected during the last batch."""
        with self._qa_metadata_lock:
            meta = dict(self._qa_metadata)
            self._qa_metadata.clear()
            return meta

    def consume_run_stats(self) -> dict[str, int]:
        """Return and reset per-run QA counters for job-level stats."""
        stats = {
            "qa_flagged": self._run_flagged,
            "qa_corrected": self._run_corrected,
            "qa_judged": self._qa_judged,
        }
        self._run_flagged = 0
        self._run_corrected = 0
        return stats

    def _store_qa_meta(self, key: str, score: int | None, issue: str | None, attempts: int) -> None:
        with self._qa_metadata_lock:
            self._qa_metadata[key] = (score, issue, attempts)

    def _report_correction(
        self,
        key: str,
        *,
        accepted: bool,
        attempt: int,
        reason: str | None = None,
        source: str = "",
        original: str = "",
        corrected: str = "",
        why: str | None = None,
    ) -> None:
        if self._progress is None:
            return
        payload: dict[str, Any] = {
            "key": key,
            "accepted": accepted,
            "attempt": attempt,
            "max_attempts": self._max_attempts,
        }
        if reason:
            payload["reason"] = reason
        if source:
            payload["source"] = source
        if original:
            payload["original"] = original
        if corrected:
            payload["corrected"] = corrected
        if why:
            payload["why"] = why
        self._progress.report("qa_correction", **payload)

    def _attempt_corrections(
        self,
        key: str,
        source: str,
        translated: str,
        verdict: Verdict,
        *,
        re_judge: bool = True,
    ) -> tuple[str | None, int]:
        """Try to correct a flagged translation up to ``max_attempts`` times.

        Three-tier strategy:

        Tier 0 — lint gate: if the original has Russian-only letters and the
        judge's fix or corrector's output removes them, accept immediately
        without re-judge (ru→uk only).

        Tier 1 — safe judge fix: if the verdict provides a structurally safe
        fix, accept it.  If the fix is structurally unsafe but passes the
        lint gate, accept it.  Otherwise re-judge; if rejected, fall through
        to the corrector rather than giving up.

        Tier 2 — corrector: use the ``retranslate_with_feedback`` API to
        produce a fresh translation with QA feedback.  Lint-gate short-circuits
        re-judge when applicable.  Stops early on the first "unchanged" result
        (subsequent attempts with the same prompt are futile).
        """
        attempts = 0
        target_lang: str = getattr(self._judge, "_target_lang", "") or ""

        # ── Tier 0+1: judge-provided fix ────────────────────────────
        if verdict.fix and verdict.fix.strip() and validate_placeholders(source, verdict.fix):
            fix = verdict.fix.strip()

            if _is_safe_fix(translated, fix):
                logger.debug("Inline QA: accepted safe judge fix for {!r}…", source[:60])
                self._report_correction(
                    key, accepted=True, attempt=0, source=source, original=translated, corrected=fix, why=verdict.why
                )
                return fix, 0

            # Lint gate: accept fix that removes Russian-only letters
            if _lint_gate_accept(fix, translated, target_lang):
                logger.debug("Inline QA: lint-gate accepted judge fix for {!r}…", source[:60])
                self._report_correction(
                    key, accepted=True, attempt=0, source=source, original=translated, corrected=fix, why=verdict.why
                )
                return fix, 0

            logger.debug("Inline QA: re-judging judge fix for {!r}…", source[:60])
            if re_judge:
                try:
                    re_verdicts = self._judge.judge_batch([(f"re:{key}", source, fix)])
                    re_v = re_verdicts.get(f"re:{key}")
                    if re_v is not None and not re_v.is_flag:
                        self._report_correction(
                            key,
                            accepted=True,
                            attempt=0,
                            source=source,
                            original=translated,
                            corrected=fix,
                            why=verdict.why,
                        )
                        return fix, 0
                    # No explanation → re-judge is unreliable, accept the fix
                    if re_v is not None and not (getattr(re_v, "why", None) or "").strip():
                        logger.info(
                            "QA re-judge judge-fix accepted (no explanation) | key={} why={!r}",
                            key,
                            getattr(re_v, "why", None),
                        )
                        self._report_correction(
                            key,
                            accepted=True,
                            attempt=0,
                            reason="re-judge no-why",
                            source=source,
                            original=translated,
                            corrected=fix,
                        )
                        return fix, 0
                    logger.info(
                        "QA re-judge judge-fix | key={} src={!r} fix={!r} → v={} score={} issue={} why={!r}",
                        key,
                        source[:80],
                        fix[:80],
                        getattr(re_v, "verdict", "?"),
                        getattr(re_v, "score", "?"),
                        getattr(re_v, "issue", "?"),
                        getattr(re_v, "why", "?"),
                    )
                except Exception as exc:
                    logger.warning("Inline QA: re-judge failed for {!r}: {}", source[:60], exc)
                    if self._progress is not None:
                        self._progress.report(
                            "qa_inline_note",
                            key=key,
                            message=f"re-judge failed, accepting fix: {exc}",
                        )
                    self._report_correction(
                        key,
                        accepted=True,
                        attempt=0,
                        reason="re-judge error",
                        source=source,
                        original=translated,
                        corrected=fix,
                    )
                    return fix, 0
                # Re-judge rejected the fix — fall through to corrector
                self._report_correction(
                    key,
                    accepted=False,
                    attempt=0,
                    reason="re-judge rejected",
                    source=source,
                    original=translated,
                    why=verdict.why,
                )
                logger.debug(
                    "Inline QA: re-judge rejected fix for {!r}, falling through to corrector",
                    source[:60],
                )
            else:
                self._report_correction(
                    key, accepted=True, attempt=0, source=source, original=translated, corrected=fix, why=verdict.why
                )
                return fix, 0

        # ── Tier 2: corrector (retranslate with feedback) ──────────
        if self._corrector is not None and hasattr(self._corrector, "retranslate_with_feedback"):
            prev_tgt = translated
            while attempts < self._max_attempts:
                attempts += 1
                try:
                    issue = verdict.issue or "unknown"
                    why = (verdict.why or "").strip()
                    if not why:
                        why = _default_why(issue)
                    corrected = self._corrector.retranslate_with_feedback(
                        source_text=source,
                        prev_tgt=prev_tgt,
                        issue=issue,
                        why=why,
                    )
                except Exception as exc:
                    logger.warning(
                        "Inline QA: corrector attempt {}/{} failed for {!r}: {}",
                        attempts,
                        self._max_attempts,
                        source[:60],
                        exc,
                    )
                    if self._progress is not None:
                        self._progress.report(
                            "qa_inline_note",
                            key=key,
                            message=f"corrector attempt {attempts}/{self._max_attempts} failed: {exc}",
                        )
                    self._report_correction(
                        key,
                        accepted=False,
                        attempt=attempts,
                        reason="error",
                        source=source,
                        original=prev_tgt,
                    )
                    continue

                if not corrected.strip():
                    self._report_correction(
                        key,
                        accepted=False,
                        attempt=attempts,
                        reason="empty",
                        source=source,
                        original=prev_tgt,
                    )
                    continue

                if corrected.strip() == prev_tgt.strip():
                    self._report_correction(
                        key,
                        accepted=False,
                        attempt=attempts,
                        reason="unchanged",
                        source=source,
                        original=prev_tgt,
                        why=verdict.why,
                    )
                    break  # subsequent attempts with same prompt are futile

                logger.info(
                    "QA corrector attempt {}/{} | key={} src={!r} → corrected={!r}",
                    attempts,
                    self._max_attempts,
                    key,
                    source[:80],
                    corrected.strip()[:120],
                )

                if not validate_placeholders(source, corrected):
                    self._report_correction(
                        key,
                        accepted=False,
                        attempt=attempts,
                        reason="placeholders",
                        source=source,
                        original=prev_tgt,
                    )
                    continue

                # Lint gate: accept corrector output that removes Russian-only letters
                if _lint_gate_accept(corrected, translated, target_lang):
                    logger.debug(
                        "Inline QA: lint-gate accepted corrector fix for {!r}…",
                        source[:60],
                    )
                    self._report_correction(
                        key,
                        accepted=True,
                        attempt=attempts,
                        source=source,
                        original=prev_tgt,
                        corrected=corrected.strip(),
                        why=verdict.why,
                    )
                    return corrected.strip(), attempts

                if not re_judge:
                    return corrected.strip(), attempts

                try:
                    re_verdicts = self._judge.judge_batch([(f"re:{key}", source, corrected.strip())])
                    re_v = re_verdicts.get(f"re:{key}")
                    if re_v is not None and not re_v.is_flag:
                        self._report_correction(
                            key,
                            accepted=True,
                            attempt=attempts,
                            source=source,
                            original=prev_tgt,
                            corrected=corrected.strip(),
                        )
                        return corrected.strip(), attempts
                    # No explanation → re-judge is unreliable, accept the correction
                    if re_v is not None and not (getattr(re_v, "why", None) or "").strip():
                        logger.info(
                            "QA re-judge corrector accepted (no explanation) | key={} attempt={} why={!r}",
                            key,
                            attempts,
                            getattr(re_v, "why", None),
                        )
                        self._report_correction(
                            key,
                            accepted=True,
                            attempt=attempts,
                            reason="re-judge no-why",
                            source=source,
                            original=prev_tgt,
                            corrected=corrected.strip(),
                        )
                        return corrected.strip(), attempts
                    logger.info(
                        "QA re-judge corrector | key={} src={!r} attempt={} "
                        "corrected={!r} → v={} score={} issue={} why={!r}",
                        key,
                        source[:80],
                        attempts,
                        corrected.strip()[:80],
                        getattr(re_v, "verdict", "?"),
                        getattr(re_v, "score", "?"),
                        getattr(re_v, "issue", "?"),
                        getattr(re_v, "why", "?"),
                    )
                except Exception as exc:
                    logger.warning(
                        "Inline QA: post-correction re-judge failed for {!r}: {}",
                        source[:60],
                        exc,
                    )
                    if self._progress is not None:
                        self._progress.report(
                            "qa_inline_note",
                            key=key,
                            message=f"post-correction re-judge failed, accepting: {exc}",
                        )
                    self._report_correction(
                        key,
                        accepted=True,
                        attempt=attempts,
                        reason="re-judge error",
                        source=source,
                        original=prev_tgt,
                        corrected=corrected.strip(),
                    )
                    return corrected.strip(), attempts

                self._report_correction(
                    key,
                    accepted=False,
                    attempt=attempts,
                    reason="re-judge rejected",
                    source=source,
                    original=prev_tgt,
                    why=verdict.why,
                )

        return None, attempts

    def _needs_correction(self, verdict: Verdict) -> bool:
        return verdict.is_flag and not (verdict.score is not None and verdict.score > self._threshold)

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
        except asyncio.CancelledError:
            return
        except Exception as exc:
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
            self._run_flagged += 1
            if self._progress is not None:
                self._progress.report(
                    "qa_verdict",
                    key=key,
                    source=source,
                    translated=translated,
                    score=score,
                    is_flagged=True,
                    issue=verdict.issue,
                    why=verdict.why,
                )

            corrected, attempts = self._attempt_corrections(key, source, translated, verdict)
            if corrected:
                normalized = _normalize_trailing_period(source, corrected)
                if normalized.strip() != translated.strip():
                    corrected_count += 1
                    self._run_corrected += 1
                    with corrections_lock:
                        corrections[key] = normalized
                    self._store_qa_meta(key, score, verdict.issue, attempts)
                    if self._progress is not None:
                        self._progress.report(
                            "qa_inline_fix",
                            key=key,
                            source=source,
                            original=translated,
                            fixed=normalized,
                            score=score,
                            issue=verdict.issue,
                            why=verdict.why,
                        )
                else:
                    self._store_qa_meta(key, score, verdict.issue, attempts)
            else:
                self._store_qa_meta(key, score, verdict.issue, attempts)

        self._qa_judged += len(batch)
        if self._progress is not None:
            self._progress.report_qa_progress(self._qa_judged, self._qa_queued)
            if flagged_count > 0 or corrected_count > 0:
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
                        work_queue.get_nowait()
                    except queue.Empty:
                        break
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

    async def translate_async(self, text: str) -> str:
        return await self._inner.translate_async(text)

    async def translate_unit_async(self, unit: TranslationUnit) -> TranslationResult:
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
            if self._progress is not None:
                self._progress.report(
                    "qa_done",
                    flagged=self._run_flagged,
                    corrected=self._run_corrected,
                )

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
