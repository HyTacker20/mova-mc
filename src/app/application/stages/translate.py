from __future__ import annotations

import asyncio
import time
from datetime import datetime
from pathlib import Path

from loguru import logger

from ...domain.models import LangFile, Mod, TranslationResult, TranslationUnit
from ...utils.cancellation import cancel_token
from ..pipeline import PipelineContext


def stage_translate(ctx: PipelineContext, mods: list[Mod]) -> list[Mod]:
    """Sync wrapper used by tests; production pipeline uses :func:`stage_translate_async`."""
    return asyncio.run(stage_translate_async(ctx, mods))


async def stage_translate_async(
    ctx: PipelineContext,
    mods: list[Mod],
    *,
    mod_index: int = 0,
    total_mod_count: int | None = None,
    entries_done_before: int = 0,
    total_entries_global: int | None = None,
) -> list[Mod]:
    result: list[Mod] = []
    selected = [m for m in mods if m.selected]
    total_mods = total_mod_count if total_mod_count is not None else len(selected)
    mods_done = 0

    # Pre-compute total entries across all selected mods for global progress
    total_entries = (
        total_entries_global
        if total_entries_global is not None
        else sum(1 for m in selected for f in m.lang_files for u in f.units if isinstance(u, TranslationUnit))
    )
    entries_done = 0
    failed_entries = 0

    for mod in mods:
        if not mod.selected:
            result.append(mod)
            continue

        cancel_token.raise_if_set()

        mod_file_count = len(mod.lang_files)
        mod_entry_count = sum(1 for f in mod.lang_files for u in f.units if isinstance(u, TranslationUnit))
        ctx.progress.report_mod_start(mod.name, mod_file_count, mod_entry_count)
        translated_files: list[LangFile] = []
        mod_translated = 0
        mod_failed = 0

        if not mod.lang_files:
            logger.info(f"No files to translate for {mod.name} — skipping")
            result.append(mod)
            continue

        effective_source = getattr(mod, "_effective_source_lang", None)
        if effective_source:
            logger.info(f"Translating {mod.name} from fallback source {effective_source}")

        for lang_file in mod.lang_files:
            cancel_token.raise_if_set()
            ctx.progress.report(
                "mod_file_start",
                mod_name=mod.name,
                file_path=str(lang_file.source_path),
                entry_count=len(lang_file.units),
            )

            source_units = [u for u in lang_file.units if isinstance(u, TranslationUnit)]
            if source_units:
                data = {u.key: u.source_text for u in source_units}
                file_total = len(data)
                file_start = time.monotonic()

                # Pre-compute total entries in this mod for fractional Mods bar
                total_in_mod = sum(1 for f in mod.lang_files for u in f.units if isinstance(u, TranslationUnit))
                entries_done_in_mod: int = 0
                progress_batch = max(1, ctx.settings.progress_batch_size)

                def _on_entry(
                    key: str,
                    source: str,
                    translated: str,
                    _ctx=ctx,
                    _mod_name: str = mod.name,
                    _base: int = entries_done_before + entries_done,
                    _total_entries: int = total_entries,
                    _total_mods: int = total_mods,
                    _mods_done: int = mod_index,
                    _total_in_mod: int = total_in_mod,
                    _failed_entries: int = failed_entries,
                ) -> None:
                    """Streaming callback — invoked per item from the provider."""
                    nonlocal entries_done_in_mod
                    entries_done_in_mod += 1
                    cumulative = _base + entries_done_in_mod
                    is_last = entries_done_in_mod >= _total_in_mod
                    should_report_bars = entries_done_in_mod % progress_batch == 0 or is_last

                    _ctx.progress.report(
                        "translated_entry",
                        key=key,
                        source=source,
                        translated=translated,
                        mod_name=_mod_name,
                    )

                    if should_report_bars:
                        _ctx.progress.report(
                            "entry_progress",
                            done=cumulative,
                            total=_total_entries,
                            mod_name=_mod_name,
                        )

                        fractional = _mods_done + min(1.0, entries_done_in_mod / max(1, _total_in_mod))
                        _ctx.progress.report(
                            "overall_progress",
                            completed_mods=_mods_done,
                            fractional_mods=fractional,
                            total_mods=_total_mods,
                            completed_entries=cumulative,
                            total_entries=_total_entries,
                            failed_entries=_failed_entries,
                        )

                    if _ctx.settings.debug or should_report_bars or entries_done_in_mod <= 3:
                        src_log = source.replace("\n", "\\n")
                        tgt_log = translated.replace("\n", "\\n")
                        logger.debug(f'    "{src_log}"  →  "{tgt_log}"')

                cancel_token.raise_if_set()
                try:
                    translated_units = await ctx.provider.translate_batch_async(
                        source_units,
                        on_entry=_on_entry,
                    )
                except Exception as exc:
                    if _is_fatal_error(exc):
                        raise
                    logger.exception(f"Batch translation failed for {lang_file.source_path}")
                    translated_units = [
                        TranslationResult(
                            unit=unit,
                            translated_text=unit.source_text,
                            success=False,
                            error="translation failed",
                        )
                        for unit in source_units
                    ]
                    for tr in translated_units:
                        _on_entry(tr.unit.key, tr.unit.source_text, tr.unit.source_text)

                qa_meta = _consume_inline_qa_metadata(ctx.provider)
                if qa_meta:
                    # Enrich results with QA metadata (TranslationResult is frozen)
                    from dataclasses import replace

                    enriched: list[TranslationResult] = []
                    for tr in translated_units:
                        meta = qa_meta.get(tr.unit.key)
                        if meta:
                            enriched.append(
                                replace(
                                    tr,
                                    qa_score=meta[0],
                                    qa_issue=meta[1],
                                    qa_attempts=meta[2],
                                )
                            )
                        else:
                            enriched.append(tr)
                    translated_units = enriched

                file_elapsed = time.monotonic() - file_start
                entries_done += file_total

                succeeded = sum(1 for u in translated_units if u.success)
                cancelled = sum(1 for u in translated_units if not u.success and u.error == "cancelled")
                failed = file_total - succeeded - cancelled
                failed_entries += failed
                mod_translated += succeeded
                mod_failed += failed
                file_duration_ms = int(file_elapsed * 1000)
                ctx.progress.report_mod_file_complete(
                    mod.name,
                    str(lang_file.source_path),
                    file_duration_ms,
                    failed,
                )
                mod_entries_done = mod_translated + mod_failed
                ctx.progress.report(
                    "overall_progress",
                    completed_mods=mod_index,
                    fractional_mods=mod_index + min(1.0, mod_entries_done / max(1, mod_entry_count)),
                    total_mods=total_mods,
                    completed_entries=entries_done_before + entries_done,
                    total_entries=total_entries,
                    failed_entries=failed_entries,
                )
                failed_info = f", {failed} failed" if failed > 0 else ""
                cancelled_info = f", {cancelled} skipped" if cancelled > 0 else ""
                source_info = f" [from {effective_source}]" if effective_source else ""
                base = f"  {lang_file.source_path.name}: {succeeded}/{file_total} translated"
                msg = f"{base}{source_info}{failed_info}{cancelled_info} in {file_elapsed:.1f}s"
                logger.info(msg)
            else:
                translated_units = []

            result_units = list(u for u in lang_file.units if isinstance(u, TranslationResult))
            translated_files.append(
                LangFile(
                    mod_name=lang_file.mod_name,
                    source_path=lang_file.source_path,
                    target_path=lang_file.target_path,
                    file_type=lang_file.file_type,
                    units=tuple(result_units + translated_units),
                )
            )

        mods_done += 1

        if not translated_files:
            logger.info(f"No translatable content in {mod.name} files — skipping")
            ctx.progress.report_mod_complete(mod.name, 0, 0, 0)
            ctx.progress.report(
                "overall_progress",
                completed_mods=mod_index + mods_done,
                total_mods=total_mods,
                completed_entries=entries_done_before + entries_done,
                total_entries=total_entries,
                failed_entries=failed_entries,
            )
            result.append(mod)
            continue

        mod_total = mod_translated + mod_failed
        ctx.progress.report_mod_complete(mod.name, mod_translated, mod_total, mod_failed)
        ctx.progress.report(
            "overall_progress",
            completed_mods=mod_index + mods_done,
            total_mods=total_mods,
            completed_entries=entries_done_before + entries_done,
            total_entries=total_entries,
            failed_entries=failed_entries,
        )

        result.append(
            Mod(
                name=mod.name,
                path=mod.path,
                lang_files=tuple(translated_files),
                selected=mod.selected,
            )
        )

    if ctx.settings.debug:
        _dump_translations(ctx, result)

    return result


def _dump_translations(ctx: PipelineContext, mods: list[Mod]) -> None:
    """Write a full translation report to a TXT file for quality checking.

    Only called when debug mode is enabled. Saves to translation_path.
    """
    try:
        out_dir = Path(ctx.settings.translation_path)
        out_dir.mkdir(parents=True, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        out_path = out_dir / f"translation_report_{ctx.settings.target_mc_lang}_{ts}.txt"

        lines: list[str] = []
        _add = lines.append

        _add("=" * 60)
        _add("  TRANSLATION QUALITY REPORT")
        _add("=" * 60)
        _add(f"  Source:      {ctx.settings.source_mc_lang}")
        _add(f"  Target:      {ctx.settings.target_mc_lang}")
        _add(f"  Provider:    {ctx.settings.provider}")
        _add(f"  Date:        {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        _add(f"  Dry run:     {ctx.settings.dry_run}")
        _add(f"  Workers:     {ctx.settings.max_workers}")
        _add("=" * 60)
        _add("")

        total_entries = 0
        total_failed = 0
        total_cached = 0

        for mod in mods:
            if not mod.selected:
                continue

            mod_entries = 0
            mod_failed = 0
            _add(f"───── Mod: {mod.name} ─────")
            _add("")

            for lang_file in mod.lang_files:
                results = [u for u in lang_file.units if isinstance(u, TranslationResult)]
                if not results:
                    continue

                _add(f"  File: {lang_file.source_path.name}")
                _add(f"       → {lang_file.target_path.name}")
                _add(f"       ({len(results)} entries)")
                _add("")

                for r in results:
                    source = r.unit.source_text
                    translated = r.translated_text
                    key = r.unit.key
                    cache_tag = " [cached]" if r.cached else ""

                    _add(f"  [{key}]{cache_tag}")
                    _add(f"    {ctx.settings.source_mc_lang}: {source}")
                    _add(f"    {ctx.settings.target_mc_lang}: {translated}")
                    if not r.success:
                        _add(f"    ⚠ FAILED{(' — ' + r.error) if r.error else ''}")
                    if r.qa_warnings:
                        for w in r.qa_warnings:
                            _add(f"    ⚑ QA: {w.get('message', w)}")
                    if r.qa_score is not None:
                        qa_tag = f" [score={r.qa_score}]"
                        if r.qa_issue:
                            qa_tag += f" ({r.qa_issue})"
                        if r.qa_attempts:
                            qa_tag += f" attempts={r.qa_attempts}"
                        _add(f"    ★{qa_tag}")
                    _add("")

                    total_entries += 1
                    mod_entries += 1
                    if not r.success:
                        total_failed += 1
                        mod_failed += 1
                    if r.cached:
                        total_cached += 1

                if lang_file.file_type != "mcfunction":
                    _add("  ── end of file ──")
                    _add("")

            if mod_entries > 0:
                _add(f"  Mod summary: {mod_entries} entries, {mod_failed} failed")
                _add("")

        _add("=" * 60)
        _add("  GLOBAL SUMMARY")
        _add("=" * 60)
        _add(f"  Total entries:    {total_entries}")
        _add(f"  Failed:           {total_failed}")
        _add(f"  Cached:           {total_cached}")
        _add(f"  Success rate:     {(total_entries - total_failed) / max(total_entries, 1) * 100:.1f}%")
        _add("=" * 60)

        out_path.write_text("\n".join(lines), encoding="utf-8")
        logger.info(f"Translation report saved: {out_path}")
    except OSError as e:
        logger.warning(f"Could not write translation report: {e}")


def _consume_inline_qa_metadata(provider: object) -> dict[str, tuple[int | None, str | None, int]]:
    """Extract QA metadata from InlineQaWrapper (possibly wrapped by CachingProvider)."""
    current = provider
    while True:
        consume = getattr(current, "consume_qa_metadata", None)
        if consume is not None:
            return consume()  # type: ignore[no-any-return]
        inner = getattr(current, "_inner", None)
        if inner is None:
            break
        current = inner
    return {}


def _translation_succeeded(source_text: str, translated_text: str) -> bool:
    """Return whether a batch translation should count as successful."""
    if not source_text.strip():
        return True
    return bool(translated_text.strip())


def _is_fatal_error(exc: Exception) -> bool:
    """Return True if this error should stop the pipeline rather than skip one mod.

    Detects rate-limit / quota / billing errors from OpenAI SDK and
    common API response patterns so we don't waste quota retrying.
    """
    # OpenAI SDK RateLimitError
    try:
        from openai import RateLimitError  # type: ignore[import-untyped]

        if isinstance(exc, RateLimitError):
            return True
    except ImportError:
        pass
    # LiteLLM / generic rate-limit patterns in error message
    msg = str(exc).lower()
    return any(
        phrase in msg
        for phrase in (
            "rate limit",
            "429",
            "usage limit",
            "quota exceeded",
            "insufficient_quota",
            "monthly usage limit",
        )
    )
