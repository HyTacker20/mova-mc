from __future__ import annotations

from pathlib import Path

from ...domain.models import Mod
from ...infrastructure.filesystem.jar_packager import convert_translated_mods
from ...utils.cancellation import cancel_token
from ..pipeline import PipelineContext


def stage_repack_jars(ctx: PipelineContext, mods: list[Mod]) -> list[Mod]:
    """Package translated files back into JAR archives.

    Converts each extracted mod directory into a .jar file, preserving
    original files alongside translated ones. Writes output to the
    configured translation_path directory. Only selected mods with
    at least one language file are packed.
    """
    cancel_token.raise_if_set()
    mod_names = [m.name for m in mods if m.selected and m.lang_files]
    output_path = Path(ctx.settings.paths.effective_output_path)
    convert_translated_mods(
        temp_path=ctx.workspace,
        translation_path=output_path,
        mods_path=Path(ctx.settings.paths.mods_path),
        target_lang=ctx.settings.target_mc_lang,
        source_lang=ctx.settings.source_mc_lang,
        mod_names=mod_names,
    )
    return mods
