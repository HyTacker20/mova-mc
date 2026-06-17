from __future__ import annotations

import asyncio
import hashlib
import json
import shutil
from dataclasses import dataclass
from pathlib import Path

from loguru import logger

from ..application.ports import ProgressSink, TranslationProvider
from ..core.settings import Settings
from ..domain.languages import get_language_english_name
from ..domain.models import LangFile, Mod, TranslationResult, TranslationUnit
from ..domain.stats import FileStats, ModStats, OverallStats
from ..infrastructure.providers.registry import AI_PROVIDERS
from ..utils.cancellation import cancel_token


def _resolve_translation_chunk_size(settings: Settings) -> int | None:
    """Return chunk_size for LLM providers: 1 = per-item, None = provider default."""
    if settings.chunk_mode == "item":
        return 1
    if settings.chunk_size is not None:
        return settings.chunk_size
    if settings.chunk_mode in ("auto", "chunk"):
        return None
    return None


def _configure_rate_limits(settings: Settings) -> None:
    from ..utils.retry_logic import global_rate_limiter

    global_rate_limiter.configure(
        rpm=settings.rate_limit_rpm,
        burst=settings.rate_limit_burst,
        services=settings.rate_limit_services,
    )


@dataclass(frozen=True)
class PipelineContext:
    """Immutable context injected into every pipeline stage.

    Holds configuration, the active translation provider, the temp workspace path,
    and a ProgressSink for event-driven progress reporting.
    """

    settings: Settings
    progress: ProgressSink
    provider: TranslationProvider
    workspace: Path


@dataclass
class PipelineResult:
    """Output of a completed pipeline run.

    Contains the accumulated OverallStats, the final mod list with translated
    LangFiles, and the workspace path for cleanup.
    """

    stats: OverallStats
    mods: list[Mod]
    workspace_path: Path


def build_context(
    settings: Settings,
    progress: ProgressSink,
    *,
    model: str | None = None,
    cache_path: str | None = None,
) -> PipelineContext:
    """Create a PipelineContext by resolving the provider from settings.

    Uses the provider name from settings to instantiate the correct translation
    service via the factory. Wraps the provider with a caching layer backed by
    SQLite to avoid re-translating identical strings across runs.

    For LLM providers, human-readable language names (e.g. "English",
    "Ukrainian") are passed so the prompt reads naturally.  Google Translate
    always receives ISO language codes.
    """
    from ..infrastructure.cache.sqlite_cache import SqliteCache
    from ..infrastructure.providers.caching import CachingProvider
    from ..infrastructure.providers.factory import get_translator_service
    from ..infrastructure.providers.glossary import load_merged_glossary
    from ..infrastructure.providers.prompts import PROMPT_VERSION
    from ..infrastructure.providers.registry import resolve_model

    _configure_rate_limits(settings)

    is_llm = settings.provider.lower() in AI_PROVIDERS

    # LLM providers get human-readable names; Google gets ISO codes
    if is_llm:
        source_lang = settings.source_mc_lang
        target_lang = settings.target_mc_lang
        source_display = get_language_english_name(settings.source_mc_lang)
        target_display = get_language_english_name(settings.target_mc_lang)
    else:
        source_lang = settings.source_google_lang
        target_lang = settings.target_google_lang
        source_display = source_lang
        target_display = target_lang

    # Load glossary (built-in + optional user glossary). Used both for prompt
    # injection (LLM providers) and for the cache signature.
    glossary = load_merged_glossary(settings.target_mc_lang, settings.glossary_path)
    glossary_sig = (
        hashlib.sha256(json.dumps(sorted(glossary.items()), ensure_ascii=True).encode()).hexdigest() if glossary else ""
    )

    db_path = cache_path or str(Path(settings.translation_path) / "translation_cache.db")
    sqlite_cache = SqliteCache(db_path)

    translation_chunk_size = _resolve_translation_chunk_size(settings)

    raw_provider: TranslationProvider = get_translator_service(
        provider=settings.provider,
        source_lang=source_lang,
        target_lang=target_lang,
        source_lang_display=source_display,
        target_lang_display=target_display,
        capitalize=True,
        max_retries=3,
        model=model,
        glossary=glossary,
        chunk_size=translation_chunk_size,
        max_concurrent_chunks=settings.max_workers,
        chunk_token_budget=settings.chunk_token_budget,
        chunk_max_text_length=settings.chunk_max_text_length,
        chunk_mode=settings.chunk_mode,
    )

    resolved_model = resolve_model(settings.provider, model)

    # ── Wrap with inline QA if enabled ─────────────────────────────
    if settings.qa_judge:
        from ..infrastructure.providers.judge import LlmJudge
        from ..infrastructure.providers.qa_wrapper import InlineQaWrapper
        from ..infrastructure.providers.registry import build_transport

        # Google + QA without dedicated judge provider: warn and skip
        if not is_llm and not settings.qa_judge_provider:
            logger.warning(
                "Inline QA: Google Translate selected but no judge provider configured. "
                "QA requires an LLM provider — set a judge provider in Advanced settings."
            )
            if progress is not None:
                progress.report_qa_warning(
                    "",
                    "QA skipped: set a judge provider for Google translation",
                )
        else:
            judge_provider = settings.qa_judge_provider or settings.provider
            judge_model = settings.qa_judge_model or resolved_model
            try:
                judge_transport = build_transport(
                    judge_provider,
                    judge_model,
                    task="judge",
                )
                judge = LlmJudge(
                    transport=judge_transport,
                    source_display=source_display,
                    target_display=target_display,
                    glossary=glossary,
                    chunk_size=settings.qa_chunk_size,
                    max_tokens=1024,
                    cache=sqlite_cache,
                    target_lang=settings.target_mc_lang,
                    judge_model=judge_model,
                    judge_workers=settings.qa_judge_workers,
                    progress=progress,
                )

                # ── Resolve corrector ──
                corrector: TranslationProvider | None = raw_provider
                if settings.qa_corrector_model:
                    try:
                        corrector = get_translator_service(
                            provider=settings.provider,
                            source_lang=source_lang,
                            target_lang=target_lang,
                            source_lang_display=source_display,
                            target_lang_display=target_display,
                            capitalize=True,
                            max_retries=3,
                            model=settings.qa_corrector_model,
                            glossary=glossary,
                            chunk_size=1,  # singleton for corrections
                            max_concurrent_chunks=1,
                        )
                    except Exception as exc:
                        logger.warning(
                            "Inline QA: failed to build corrector with model {}, falling back to translator: {}",
                            settings.qa_corrector_model,
                            exc,
                        )

                raw_provider = InlineQaWrapper(
                    inner=raw_provider,
                    judge=judge,
                    corrector=corrector,
                    threshold=settings.qa_threshold,
                    max_attempts=settings.qa_max_attempts,
                    chunk_size=settings.qa_chunk_size,
                    progress=progress,
                )
            except Exception as exc:
                logger.warning(
                    "Inline QA: failed to build judge ({}/{}), skipping inline QA: {}",
                    judge_provider,
                    judge_model,
                    exc,
                )

    if settings.no_cache:
        provider: TranslationProvider = raw_provider
    else:
        provider = CachingProvider(
            inner=raw_provider,
            cache=sqlite_cache,
            source_lang=source_lang,
            target_lang=target_lang,
            provider_name=settings.provider,
            model=resolved_model,
            prompt_version=PROMPT_VERSION,
            glossary_signature=glossary_sig,
            no_cache=settings.no_cache,
        )

    workspace = Path(settings.temp_path)

    return PipelineContext(
        settings=settings,
        progress=progress,
        provider=provider,
        workspace=workspace,
    )


# ── Sync pipeline runner ───────────────────────────────────────────


async def run_pipeline_async(ctx: PipelineContext, mods: list[Mod]) -> PipelineResult:
    """Async version of :func:`run_pipeline`.

    Processes each mod through the full pipeline individually
    (unpack → discover → parse → translate → validate → write → repack)
    before moving to the next.  This gives faster perceived progress
    and keeps memory usage bounded to one mod at a time.
    """
    from .stages.discover import stage_discover_files
    from .stages.parse import stage_parse_sources
    from .stages.repack import stage_repack_jars
    from .stages.resourcepack import stage_build_resourcepack
    from .stages.translate import stage_translate_async
    from .stages.unpack import stage_unpack_jars
    from .stages.validate import stage_validate_outputs
    from .stages.write import stage_write_targets

    if ctx.workspace.exists():
        shutil.rmtree(ctx.workspace, ignore_errors=True)
        ctx.workspace.mkdir(parents=True, exist_ok=True)

    stats = OverallStats()
    stats.start()

    selected = [m for m in mods if m.selected]
    total_mods = len(selected)
    completed_mods: list[Mod] = []
    failed_mod_names: list[str] = []
    resource_pack_mods: list[Mod] = []

    # Pre-compute total entries for overall progress denominator.
    # Mods arrive from the scanner with lang_files=() — the actual units
    # are discovered during parse.  Use _estimated_entries (attached by
    # modinfo_to_domain_mod) as a close-enough denominator for the
    # progress bars until the translate stage reports real totals.
    total_entries = sum(getattr(m, "_estimated_entries", 0) for m in selected)
    cumulative_entries = 0

    for idx, mod in enumerate(selected):
        cancel_token.raise_if_set()

        mod_name = mod.name
        ctx.progress.report("title", text=f"Processing {mod_name} ({idx + 1}/{total_mods})...")
        ctx.progress.report(
            "overall_progress",
            completed_mods=idx,
            fractional_mods=float(idx),
            total_mods=total_mods,
            completed_entries=cumulative_entries,
            total_entries=total_entries,
            failed_entries=0,
        )

        try:
            # ── 1. Unpack ──
            ctx.progress.report("title", text=f"Unpacking {mod_name}...")
            [processed] = await asyncio.to_thread(stage_unpack_jars, ctx, [mod])

            # ── 2. Discover ──
            ctx.progress.report("title", text=f"Discovering files in {mod_name}...")
            [processed] = await asyncio.to_thread(stage_discover_files, ctx, [processed])

            if not processed.lang_files:
                logger.info(f"No language files in {mod_name} — skipping")
                completed_mods.append(processed)
                continue

            # ── 3. Parse ──
            ctx.progress.report("title", text=f"Parsing {mod_name}...")
            [processed] = await asyncio.to_thread(stage_parse_sources, ctx, [processed])

            # ── 4. Translate ──
            ctx.progress.report("title", text=f"Translating {mod_name}...")
            [processed] = await stage_translate_async(
                ctx,
                [processed],
                mod_index=idx,
                total_mod_count=total_mods,
                entries_done_before=cumulative_entries,
                total_entries_global=total_entries,
            )

            # ── 5. Validate ──
            ctx.progress.report("title", text=f"Validating {mod_name}...")
            [processed] = await asyncio.to_thread(stage_validate_outputs, ctx, [processed])

            # ── Count entries in this mod for cumulative tracking ──
            mod_entry_count = sum(len(f.units) for f in processed.lang_files)
            cumulative_entries += mod_entry_count

            if ctx.settings.dry_run:
                logger.info(f"Dry run — skipping write/repack for {mod_name}")
            elif ctx.settings.output_mode == "resourcepack":
                # ── 6. Write targets ──
                [processed] = await asyncio.to_thread(stage_write_targets, ctx, [processed])
                resource_pack_mods.append(processed)
            else:
                # ── 6. Write targets ──
                [processed] = await asyncio.to_thread(stage_write_targets, ctx, [processed])
                # ── 7. Repack ──
                ctx.progress.report("title", text=f"Repacking {mod_name}...")
                [processed] = await asyncio.to_thread(stage_repack_jars, ctx, [processed])

            completed_mods.append(processed)

        except asyncio.CancelledError:
            # Preserve already-completed mods in the result so callers
            # can report partial progress; re-raise for the job runner.
            logger.info(f"Cancelled during {mod_name} — {len(completed_mods)} mod(s) already complete")
            raise
        except Exception as exc:
            if _is_fatal_pipeline_error(exc):
                raise
            logger.exception(f"Failed to process mod {mod_name} — skipping")
            failed_mod_names.append(mod_name)
            continue

    # ── Resource pack: build once at the end ──
    if ctx.settings.output_mode == "resourcepack" and not ctx.settings.dry_run:
        if resource_pack_mods:
            ctx.progress.report("title", text="Building resource pack...")
            await asyncio.to_thread(stage_build_resourcepack, ctx, resource_pack_mods)
        else:
            logger.warning("No mods with language files — resource pack skipped")

    # ── Collect inline QA stats from wrapper (accumulated across all mods) ──
    _collect_inline_qa_stats(ctx.provider, stats)

    _accumulate_stats(stats, completed_mods)

    if failed_mod_names:
        logger.warning(f"Skipped {len(failed_mod_names)} failed mod(s): {', '.join(failed_mod_names)}")

    stats.finish()
    stats.provider = ctx.settings.provider
    stats.source_lang = ctx.settings.source_mc_lang
    stats.target_lang = ctx.settings.target_mc_lang

    return PipelineResult(stats=stats, mods=completed_mods, workspace_path=ctx.workspace)


def run_pipeline(ctx: PipelineContext, mods: list[Mod]) -> PipelineResult:
    """Execute the full translation pipeline (sync wrapper for CLI)."""
    return asyncio.run(run_pipeline_async(ctx, mods))


def _collect_inline_qa_stats(provider: object, stats: OverallStats) -> None:
    """Walk the provider chain and collect QA stats from InlineQaWrapper."""
    current = provider
    while True:
        if hasattr(current, "consume_run_stats"):
            qa_stats = current.consume_run_stats()  # type: ignore[union-attr]
            if isinstance(qa_stats, dict) and qa_stats.get("qa_judged", 0) > 0:
                stats.qa_enabled = True
                stats.qa_judged = qa_stats.get("qa_judged", 0)
                stats.qa_flagged = qa_stats.get("qa_flagged", 0)
                stats.qa_corrected = qa_stats.get("qa_corrected", 0)
            return
        inner = getattr(current, "_inner", None)
        if inner is None:
            break
        current = inner


def _accumulate_stats(stats: OverallStats, mods: list[Mod]) -> None:
    for mod in mods:
        if not mod.selected:
            continue

        mod_stats = ModStats(name=mod.name)
        mod_stats.start()

        for lang_file in mod.lang_files:
            file_stats = _build_file_stats(lang_file)
            mod_stats.files.append(file_stats)

        mod_stats.finish()
        if mod_stats.total_entries == 0:
            mod_stats.skipped = True
        stats.mods.append(mod_stats)


def _build_file_stats(lang_file: LangFile) -> FileStats:
    file_stats = FileStats(path=str(lang_file.source_path), file_type=lang_file.file_type)
    file_stats.entries_total = len(lang_file.units)

    translated = 0
    failed = 0
    for unit in lang_file.units:
        if isinstance(unit, TranslationResult):
            if unit.success:
                translated += 1
            else:
                failed += 1
        elif isinstance(unit, TranslationUnit):
            pass

    file_stats.entries_translated = translated
    file_stats.entries_failed = failed
    return file_stats


def _is_fatal_pipeline_error(exc: Exception) -> bool:
    """Re-export of :func:`app.application.stages.translate._is_fatal_error`.

    Avoids an import cycle between pipeline and translate stages.
    """
    from .stages.translate import _is_fatal_error  # type: ignore[import-untyped]

    return _is_fatal_error(exc)
