"""Pipeline stage that assembles translated language files into a Minecraft resource pack."""

from __future__ import annotations

from pathlib import Path

from loguru import logger

from ...domain.models import Mod
from ...infrastructure.filesystem.resourcepack_builder import build_resource_pack
from ...utils.cancellation import cancel_token
from ..pipeline import PipelineContext


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

    # Pack name: e.g. "mova_uk_UA"
    pack_name = f"mova_{target_lang}"

    ctx.progress.report("title", text="Building resource pack...")

    zip_path = build_resource_pack(
        workspace=ctx.workspace,
        output_dir=output_path,
        target_lang=target_lang,
        pack_name=pack_name,
    )

    logger.info("Resource pack ready: {}", zip_path)
    return mods
