"""Pipeline stage that assembles translated language files into a Minecraft resource pack."""

from __future__ import annotations

from pathlib import Path

from loguru import logger

from ...domain.languages import get_language_english_name
from ...domain.models import Mod
from ...infrastructure.filesystem.resourcepack_builder import build_resource_pack
from ...utils.cancellation import cancel_token
from ..pipeline import PipelineContext


def _build_pack_name(lang_code: str, mod_count: int) -> str:
    """Build a human-friendly resource pack filename.

    Examples:
        ``_build_pack_name("uk_UA", 3)`` → ``"Ukrainian — 3 mods (MovaMC)"``
        ``_build_pack_name("es_ES", 1)`` → ``"Spanish — 1 mod (MovaMC)"``
    """
    lang = get_language_english_name(lang_code)
    mods_word = "mod" if mod_count == 1 else "mods"
    return f"{lang} — {mod_count} {mods_word} (MovaMC)"


def stage_build_resourcepack(ctx: PipelineContext, mods: list[Mod]) -> list[Mod]:
    """Build a Minecraft resource pack .zip from translated language files.

    Collects translated ``{target_lang}.json`` / ``{target_lang}.lang``
    files from the workspace and packs them into a standard resource pack
    zip alongside ``pack.mcmeta``.
    """
    cancel_token.raise_if_set()

    selected = [m for m in mods if m.selected and m.lang_files]
    if not selected:
        logger.warning("No mods with language files to include — resource pack will be empty")
    else:
        logger.info(f"Building resource pack from {len(selected)} mod(s)")

    output_path = Path(ctx.settings.effective_output_path())
    target_lang = ctx.settings.target_mc_lang

    pack_name = _build_pack_name(target_lang, len(selected))

    ctx.progress.report("title", text="Building resource pack...")

    zip_path = build_resource_pack(
        workspace=ctx.workspace,
        output_dir=output_path,
        target_lang=target_lang,
        pack_name=pack_name,
    )

    logger.info("Resource pack ready: {}", zip_path)
    return mods
