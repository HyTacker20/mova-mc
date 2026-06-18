"""Pipeline stage that assembles translated language files into a Minecraft resource pack."""

from __future__ import annotations

from pathlib import Path

from loguru import logger

from ...domain.languages import get_language_english_name
from ...domain.models import Mod, TranslationResult
from ...infrastructure.filesystem.resourcepack_builder import build_resource_pack
from ...utils.cancellation import cancel_token
from ..pipeline import PipelineContext


def _build_pack_name(lang_code: str) -> str:
    """Build a human-friendly resource pack filename.

    Examples:
        ``_build_pack_name("uk_UA")`` → ``"Ukrainian (MovaMC)"``
    """
    lang = get_language_english_name(lang_code)
    return f"{lang} (MovaMC)"


def _build_description(
    lang_code: str,
    mod_count: int,
    entry_count: int,
    provider: str,
) -> str:
    """Build a concise pack.mcmeta description.

    Examples:
        ``_build_description("uk_UA", 3, 127, "opencode")``
        → ``"Ukrainian · 3 mods · 127 entries · via OpenCode"``
    """
    lang = get_language_english_name(lang_code)
    entries_word = "entry" if entry_count == 1 else "entries"
    return f"{lang} · {mod_count} mods · {entry_count} {entries_word} · via {provider}"


def _count_entries(mods: list[Mod]) -> int:
    """Count total translated entries across selected mods."""
    total = 0
    for mod in mods:
        if not mod.selected or not mod.lang_files:
            continue
        for lf in mod.lang_files:
            total += sum(1 for u in lf.units if isinstance(u, TranslationResult))
    return total


def stage_build_resourcepack(ctx: PipelineContext, mods: list[Mod]) -> list[Mod]:
    """Build a Minecraft resource pack .zip from translated language files."""
    cancel_token.raise_if_set()

    selected = [m for m in mods if m.selected and m.lang_files]
    if not selected:
        logger.warning("No mods with language files to include — resource pack will be empty")

    output_path = Path(ctx.settings.paths.effective_output_path)
    target_lang = ctx.settings.target_mc_lang
    entry_count = _count_entries(mods)

    pack_name = _build_pack_name(target_lang)
    description = _build_description(
        target_lang,
        len(selected),
        entry_count,
        ctx.settings.provider,
    )

    ctx.progress.report("title", text="Building resource pack...")

    zip_path = build_resource_pack(
        workspace=ctx.workspace,
        output_dir=output_path,
        target_lang=target_lang,
        pack_name=pack_name,
        description=description,
    )

    logger.info("Resource pack ready: {}", zip_path)
    return mods
