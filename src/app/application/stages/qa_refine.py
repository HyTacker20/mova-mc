"""QA refinement stage — LLM judge scores translations and selectively
re-translates flagged entries.

This stage sits between translate and validate in the pipeline. It is
strictly non-blocking: any judge/transport error degrades gracefully
and the original translation is preserved.
"""

from __future__ import annotations

import asyncio
from typing import Any

from loguru import logger

from ...domain.models import LangFile, Mod, TranslationResult
from ...domain.placeholders import validate_placeholders
from ...utils.cancellation import cancel_token
from ..pipeline import PipelineContext
from .validate import _validate_result


def _get_judge_model(ctx: PipelineContext) -> str:
    """Resolve the actual judge model name from settings.

    Mirrors the logic at the top of :func:`stage_qa_refine`.
    """
    from ...infrastructure.providers.registry import _resolve_model

    if ctx.settings.qa_judge_model:
        return ctx.settings.qa_judge_model
    if not ctx.settings.qa_judge_provider:
        # Same provider as translator → use translator's actual model
        return ctx.settings.model or _resolve_model(ctx.settings.provider)
    return _resolve_model(ctx.settings.qa_judge_provider)


def _get_verdict_cache(ctx: PipelineContext) -> Any | None:
    """Return the SQLite cache from CachingProvider, if present."""
    cache = getattr(ctx.provider, "_cache", None)
    if cache is not None and hasattr(cache, "get_verdict"):
        return cache
    return None


def _get_corrector(ctx: PipelineContext) -> Any | None:
    """Return the inner provider for re-translation, or None if not available.

    Unwraps ``CachingProvider._inner`` and checks for the
    ``retranslate_with_feedback`` method.
    """
    inner = getattr(ctx.provider, "_inner", ctx.provider)
    if hasattr(inner, "retranslate_with_feedback"):
        return inner
    return None


def stage_qa_refine(ctx: PipelineContext, mods: list[Mod]) -> list[Mod]:
    """Run the QA judge over translated entries and re-translate flags.

    When ``ctx.settings.qa_judge`` is False, returns mods unchanged.
    """
    if not ctx.settings.qa_judge:
        return mods

    # ── Build judge ─────────────────────────────────────────────────────
    judge_provider = ctx.settings.qa_judge_provider or ctx.settings.provider
    judge_model = _get_judge_model(ctx)

    try:
        from ...infrastructure.providers.judge import LlmJudge, display_score
        from ...infrastructure.providers.registry import build_transport

        transport = build_transport(judge_provider, judge_model)
    except Exception:
        logger.warning("QA judge: failed to build transport for {} ({}), skipping QA", judge_provider, judge_model)
        return mods

    inner = getattr(ctx.provider, "_inner", None)
    if inner is not None:
        source_display = getattr(inner, "source_lang_display", ctx.settings.source_mc_lang)
        target_display = getattr(inner, "target_lang_display", ctx.settings.target_mc_lang)
    else:
        source_display = ctx.settings.source_mc_lang
        target_display = ctx.settings.target_mc_lang

    from ...infrastructure.providers.glossary import load_merged_glossary

    merged_glossary = load_merged_glossary(ctx.settings.target_mc_lang, ctx.settings.glossary_path)

    judge = LlmJudge(
        transport=transport,
        source_display=source_display,
        target_display=target_display,
        glossary=merged_glossary,
        chunk_size=ctx.settings.qa_chunk_size,
        judge_workers=ctx.settings.qa_judge_workers,
        cache=_get_verdict_cache(ctx),
        target_lang=ctx.settings.target_mc_lang,
        judge_model=judge_model,
    )

    corrector = _get_corrector(ctx)

    threshold = ctx.settings.qa_threshold
    max_attempts = ctx.settings.qa_max_attempts

    # ── Collect candidates ──────────────────────────────────────────────
    candidates: list[tuple[int, int, int, TranslationResult]] = []

    for mi, mod in enumerate(mods):
        if not mod.selected:
            continue
        for fi, lang_file in enumerate(mod.lang_files):
            for ri, unit in enumerate(lang_file.units):
                if not isinstance(unit, TranslationResult):
                    continue
                if not unit.success:
                    continue
                tgt = unit.translated_text.strip()
                src = unit.unit.source_text.strip()
                if not tgt or tgt == src:
                    continue
                candidates.append((mi, fi, ri, unit))

    if not candidates:
        logger.info("QA judge: no candidates to review")
        return mods

    cancel_token.raise_if_set()
    ctx.progress.report_qa_start(len(candidates), judge_provider, judge_model)
    logger.info("QA judge: reviewing {} entries via {} ({})", len(candidates), judge_provider, judge_model)

    # ── Judge batch ─────────────────────────────────────────────────────
    items = [
        (
            f"{mi}:{fi}:{ri}",
            unit.unit.source_text,
            unit.translated_text,
        )
        for mi, fi, ri, unit in candidates
    ]
    judge_key_to_pos = {
        item[0]: (mi, fi, ri, unit)
        for item, (mi, fi, ri, unit) in zip(items, candidates, strict=True)
    }

    try:
        verdicts = judge.judge_batch(items)
    except Exception:
        logger.exception("QA judge: batch judgement failed, skipping QA")
        return mods

    flagged_count = sum(1 for v in verdicts.values() if v.is_flag)
    logger.info("QA judge: flagged {} of {} entries", flagged_count, len(verdicts))

    # ── Process flagged entries ─────────────────────────────────────────
    new_mods: list[Mod] = list(mods)

    for judge_key, verdict in verdicts.items():
        mi, fi, ri, old_result = judge_key_to_pos[judge_key]

        src = old_result.unit.source_text
        ctx.progress.report_qa_verdict(
            key=old_result.unit.key,
            score=display_score(verdict),
            is_flagged=verdict.is_flag,
            issue=verdict.issue,
        )

        if not verdict.is_flag:
            new_result = TranslationResult(
                unit=old_result.unit,
                translated_text=old_result.translated_text,
                success=old_result.success,
                cached=old_result.cached,
                error=old_result.error,
                qa_warnings=old_result.qa_warnings,
                qa_score=verdict.score or 5,
                qa_issue=None,
                qa_attempts=old_result.qa_attempts,
            )
            _replace_result_in_mods(new_mods, mi, fi, ri, new_result)
            continue

        src = old_result.unit.source_text
        prev_tgt = old_result.translated_text

        # Check if already at/below threshold after previous attempts
        if verdict.score is not None and verdict.score > threshold:
            new_result = TranslationResult(
                unit=old_result.unit,
                translated_text=old_result.translated_text,
                success=old_result.success,
                cached=old_result.cached,
                error=old_result.error,
                qa_warnings=old_result.qa_warnings,
                qa_score=verdict.score,
                qa_issue=verdict.issue,
                qa_attempts=old_result.qa_attempts,
            )
            _replace_result_in_mods(new_mods, mi, fi, ri, new_result)
            continue

        # ── Attempt correction ──────────────────────────────────────────
        accepted: str | None = None
        best_text: str = prev_tgt
        best_score: int = verdict.score or 1
        attempts = 0

        # Strategy 1: Use judge's fix if valid
        if verdict.fix and verdict.fix.strip() and validate_placeholders(src, verdict.fix):
            accepted = verdict.fix.strip()
            ctx.progress.report_qa_correction(
                key=old_result.unit.key,
                accepted=True,
                attempt=0,
                max_attempts=1,
            )
            logger.debug("QA: accepted judge fix for '{}'", old_result.unit.key)

        # Strategy 2: Use corrector if available
        if accepted is None and corrector is not None:
            attempt = 0
            while attempt < max_attempts and accepted is None:
                attempt += 1
                attempts += 1
                try:
                    corrected = corrector.retranslate_with_feedback(
                        source_text=src,
                        prev_tgt=prev_tgt,
                        issue=verdict.issue or "unknown",
                        why=verdict.why or "",
                    )
                except Exception:
                    logger.warning(
                        "QA corrector attempt {}/{} failed for '{}'",
                        attempt,
                        max_attempts,
                        old_result.unit.key,
                    )
                    continue

                if not corrected.strip() or corrected.strip() == prev_tgt.strip():
                    continue

                # Validate placeholders
                if not validate_placeholders(src, corrected):
                    logger.debug("QA: corrector attempt {} broke placeholders for '{}'", attempt, old_result.unit.key)
                    continue

                # Re-judge the corrected text (single item)
                try:
                    re_judge = judge.judge_batch([(f"re:{mi}:{fi}:{ri}", src, corrected)])
                    re_v = re_judge.get(f"re:{mi}:{fi}:{ri}")
                    if re_v is not None:
                        if re_v.verdict == "ok":
                            accepted = corrected.strip()
                            ctx.progress.report_qa_correction(
                                key=old_result.unit.key,
                                accepted=True,
                                attempt=attempt,
                                max_attempts=max_attempts,
                            )
                            logger.debug("QA: corrector accepted on attempt {}", attempt)
                            break
                        if re_v.score is not None and re_v.score > best_score:
                            best_text = corrected.strip()
                            best_score = re_v.score
                            logger.debug("QA: corrector improved score to {} on attempt {}", re_v.score, attempt)
                except Exception:
                    logger.warning("QA: re-judge failed for corrected text of '{}'", old_result.unit.key)
                    ctx.progress.report_qa_correction(
                        key=old_result.unit.key,
                        accepted=True,
                        attempt=attempt,
                        max_attempts=max_attempts,
                    )
                    accepted = corrected.strip()
                    break

        # Finalise
        final_text = accepted if accepted is not None else best_text
        new_result = TranslationResult(
            unit=old_result.unit,
            translated_text=final_text,
            success=accepted is not None or old_result.success,
            cached=old_result.cached,
            error=old_result.error,
            qa_warnings=old_result.qa_warnings,
            qa_score=verdict.score,
            qa_issue=verdict.issue if accepted is None else None,
            qa_attempts=old_result.qa_attempts + attempts,
        )
        new_result = _validate_result(
            new_result,
            ctx=ctx,
            run_uk_lint=ctx.settings.target_mc_lang == "uk_UA",
        )
        _replace_result_in_mods(new_mods, mi, fi, ri, new_result)

        # ── Recache the corrected text ─────────────────────────────────
        if accepted is not None and hasattr(ctx.provider, "recache"):
            try:
                ctx.provider.recache(src, accepted)
                logger.info("QA: recached corrected translation for '{}'", old_result.unit.key)
            except Exception as _recache_exc:
                logger.warning(
                    "QA: failed to recache corrected translation for '{}': {}",
                    old_result.unit.key, _recache_exc,
                )

        # ── Store verdict ──────────────────────────────────────────────
        _store_verdict(ctx, src, final_text, verdict, attempts)

    # ── Summary ────────────────────────────────────────────────────────
    corrected = sum(
        1
        for vk, v in verdicts.items()
        if v.is_flag
        and (result := _get_result(new_mods, *judge_key_to_pos[vk][:3])) is not None
        and result.translated_text != judge_key_to_pos[vk][3].translated_text  # type: ignore[arg-type]
    )
    logger.info(
        "QA judge complete: {} flagged, {} corrected (threshold={}, max_attempts={})",
        flagged_count,
        corrected,
        threshold,
        max_attempts,
    )

    ctx.progress.report_qa_done(flagged=flagged_count, corrected=corrected)

    return new_mods


def _get_result(mods: list[Mod], mi: int, fi: int, ri: int) -> TranslationResult | None:
    """Get a specific TranslationResult from the mod list by index."""
    if mi >= len(mods):
        return None
    mod = mods[mi]
    if fi >= len(mod.lang_files):
        return None
    lang_file = mod.lang_files[fi]
    if ri >= len(lang_file.units):
        return None
    unit = lang_file.units[ri]
    if isinstance(unit, TranslationResult):
        return unit
    return None


def _replace_result_in_mods(mods: list[Mod], mi: int, fi: int, ri: int, new_result: TranslationResult) -> None:
    """Replace a single TranslationResult in the mods list, creating new
    immutable LangFile/Mod instances as needed."""
    mod = mods[mi]
    lang_file = mod.lang_files[fi]
    old_units = list(lang_file.units)
    old_units[ri] = new_result
    new_lang_file = LangFile(
        mod_name=lang_file.mod_name,
        source_path=lang_file.source_path,
        target_path=lang_file.target_path,
        file_type=lang_file.file_type,
        units=tuple(old_units),
    )
    new_files = list(mod.lang_files)
    new_files[fi] = new_lang_file
    mods[mi] = Mod(
        name=mod.name,
        path=mod.path,
        lang_files=tuple(new_files),
        selected=mod.selected,
    )


def _store_verdict(
    ctx: PipelineContext,
    src: str,
    final_text: str,
    verdict: Any,
    attempts: int,
) -> None:
    """Store the QA verdict in the verdict cache if available."""
    try:
        from ...infrastructure.providers.judge import build_verdict_cache_key

        cache = getattr(ctx.provider, "_cache", None)
        if cache is not None and hasattr(cache, "set_verdict"):
            judge_model = _get_judge_model(ctx)
            vkey = build_verdict_cache_key(src, final_text, ctx.settings.target_mc_lang, judge_model)
            cache.set_verdict(
                key=vkey,
                verdict=verdict.verdict,
                score=verdict.score,
                issue=verdict.issue,
                attempts=attempts,
            )
    except Exception:
        logger.warning("QA: failed to store verdict in cache")


async def stage_qa_refine_async(ctx: PipelineContext, mods: list[Mod]) -> list[Mod]:
    """Async wrapper for :func:`stage_qa_refine`."""
    return await asyncio.to_thread(stage_qa_refine, ctx, mods)
