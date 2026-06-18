from __future__ import annotations

from pathlib import Path

from ...domain.models import Mod
from ...infrastructure.filesystem.jar_unpacker import unpack_mods
from ...utils.cancellation import cancel_token
from ..pipeline import PipelineContext


def stage_unpack_jars(ctx: PipelineContext, mods: list[Mod]) -> list[Mod]:
    """Extract selected mod JARs into the pipeline workspace.

    Uses the Mod.path (JAR location) and writes extracted contents under
    workspace/mod_name/. Mod objects are returned unchanged.
    """
    cancel_token.raise_if_set()
    selected_names = [m.name for m in mods if m.selected]
    unpack_mods(Path(ctx.settings.paths.mods_path), ctx.workspace, selected_mods=selected_names)
    return mods
