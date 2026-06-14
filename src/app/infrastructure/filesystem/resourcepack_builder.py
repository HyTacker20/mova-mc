"""Resource pack builder — assemble translated language files into a Minecraft resource pack.

The workspace already has the correct ``assets/<namespace>/lang/`` layout from the
unpack stage. We walk the workspace, collect translated ``{target_lang}.json`` /
``{target_lang}.lang`` files, preserve their directory structure inside the zip,
and add a ``pack.mcmeta``.
"""

from __future__ import annotations

import json
import zipfile
from pathlib import Path

from loguru import logger

PACK_MCMETA = {
    "pack": {
        "pack_format": 15,
        "description": "MovaMC Translation Pack",
    }
}
"""Default ``pack.mcmeta`` contents targetting Minecraft 1.20+."""


def write_pack_mcmeta(zf: zipfile.ZipFile) -> None:
    """Write ``pack.mcmeta`` into an open zip file."""
    zf.writestr("pack.mcmeta", json.dumps(PACK_MCMETA, indent=2, ensure_ascii=False))


def build_resource_pack(
    workspace: Path,
    output_dir: Path,
    target_lang: str,
    pack_name: str,
) -> Path:
    """Walk *workspace* and collect translated files into a resource pack zip.

    Parameters
    ----------
    workspace:
        Temp directory containing per-mod extracted directories with
        ``assets/<ns>/lang/`` trees.
    output_dir:
        Directory where the output ``.zip`` is created.
    target_lang:
        Target language code (e.g. ``"uk_UA"``, ``"es_ES"``).
    pack_name:
        Base name for the zip (without extension) — e.g.
        ``"mova_uk_UA"``.

    Returns
    -------
    Path
        Absolute path to the created ``.zip`` file.
    """
    target_lang_lower = target_lang.lower()
    extensions = {".json", ".lang"}

    output_path = output_dir / f"{pack_name}.zip"
    output_dir.mkdir(parents=True, exist_ok=True)

    collected: list[tuple[str, Path]] = []  # (arcname, file_path)
    for entry in sorted(workspace.rglob("*")):
        if not entry.is_file():
            continue
        # Only collect translated language files (not source-lang files, not unrelated files)
        stem_lower = entry.stem.lower()
        if stem_lower != target_lang_lower:
            continue
        if entry.suffix.lower() not in extensions:
            continue

        # Preserve structure inside zip: strip the per-mod prefix.
        # workspace/<mod_name>/assets/.../lang/uk_ua.json
        #   →            assets/.../lang/uk_ua.json
        rel = entry.relative_to(workspace)
        collected.append((str(rel), entry))

    if not collected:
        logger.warning(
            "No target-language files found in workspace for lang={} — "
            "resource pack will contain only pack.mcmeta",
            target_lang,
        )

    with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as zf:
        write_pack_mcmeta(zf)
        for arcname, file_path in collected:
            logger.debug("Adding {} → {}", file_path, arcname)
            zf.write(file_path, arcname)

    logger.info(
        "Resource pack written: {} ({} files)",
        output_path,
        len(collected),
    )
    return output_path
