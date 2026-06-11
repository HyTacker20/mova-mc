from __future__ import annotations

import asyncio
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


def _resolve_translation_chunk_size(settings: Settings) -> int | None:
    """Return chunk_size for LLM providers: 0 = per-item, None = provider default."""
    if settings.chunk_mode == "item":
        return 0
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
    from ..infrastructure.providers.registry import _resolve_model

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
    glossary_sig = str(hash(frozenset(glossary.items()))) if glossary else ""

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
    )

    resolved_model = _resolve_model(settings.provider, model)

    # ── Wrap with inline QA (streaming) if enabled ─────────────────
    if settings.qa_judge and settings.qa_streaming and is_llm:
        from ..infrastructure.providers.judge import LlmJudge
        from ..infrastructure.providers.qa_wrapper import InlineQaWrapper
        from ..infrastructure.providers.registry import build_transport

        judge_provider = settings.qa_judge_provider or settings.provider
        judge_model = settings.qa_judge_model or resolved_model
        try:
            judge_transport = build_transport(judge_provider, judge_model)
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
            )
            raw_provider = InlineQaWrapper(
                inner=raw_provider,
                judge=judge,
                corrector=raw_provider,
                threshold=settings.qa_threshold,
                max_attempts=settings.qa_max_attempts,
                chunk_size=settings.qa_chunk_size,
                progress=progress,
            )
            progress.report(
                "qa_inline_status",
                provider=judge_provider,
                model=judge_model,
            )
        except Exception:
            logger.warning(
                "Inline QA: failed to build judge ({}/{}), skipping streaming QA",
                judge_provider,
                judge_model,
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

    All stages run the same sync implementations except ``translate``,
    which uses the async provider methods for non-blocking I/O.
    """
    from .stages.discover import stage_discover_files
    from .stages.parse import stage_parse_sources
    from .stages.qa_refine import stage_qa_refine_async
    from .stages.repack import stage_repack_jars
    from .stages.translate import stage_translate_async
    from .stages.unpack import stage_unpack_jars
    from .stages.validate import stage_validate_outputs
    from .stages.write import stage_write_targets

    if ctx.workspace.exists():
        shutil.rmtree(ctx.workspace, ignore_errors=True)
        ctx.workspace.mkdir(parents=True, exist_ok=True)

    stats = OverallStats()
    stats.start()

    ctx.progress.report("title", text="Unpacking mods...")
    mods = await asyncio.to_thread(stage_unpack_jars, ctx, mods)

    ctx.progress.report("title", text="Discovering language files...")
    mods = await asyncio.to_thread(stage_discover_files, ctx, mods)

    ctx.progress.report("title", text="Parsing source files...")
    mods = await asyncio.to_thread(stage_parse_sources, ctx, mods)

    ctx.progress.report("title", text="Translating...")
    mods = await stage_translate_async(ctx, mods)

    if ctx.settings.qa_judge and ctx.settings.qa_streaming:
        ctx.progress.report(
            "qa_inline_status",
            provider="",
            model="",
            message="Inline QA handled corrections — skipping batch QA review",
        )
    else:
        ctx.progress.report("title", text="QA review...")
        mods = await stage_qa_refine_async(ctx, mods)

    ctx.progress.report("title", text="Validating translations...")
    mods = await asyncio.to_thread(stage_validate_outputs, ctx, mods)

    if ctx.settings.dry_run:
        logger.info("Dry run enabled — skipping write and repack stages")
        ctx.progress.report("title", text="Dry run complete (no files written)")
    else:
        ctx.progress.report("title", text="Writing target files...")
        mods = await asyncio.to_thread(stage_write_targets, ctx, mods)

        ctx.progress.report("title", text="Repacking JARs...")
        mods = await asyncio.to_thread(stage_repack_jars, ctx, mods)

    _accumulate_stats(stats, mods)

    stats.finish()
    stats.provider = ctx.settings.provider
    stats.source_lang = ctx.settings.source_mc_lang
    stats.target_lang = ctx.settings.target_mc_lang

    return PipelineResult(stats=stats, mods=mods, workspace_path=ctx.workspace)


def run_pipeline(ctx: PipelineContext, mods: list[Mod]) -> PipelineResult:
    """Execute the full translation pipeline (sync wrapper for CLI)."""
    return asyncio.run(run_pipeline_async(ctx, mods))


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


