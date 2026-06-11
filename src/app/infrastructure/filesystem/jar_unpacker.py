from __future__ import annotations

import zipfile
from pathlib import Path

from loguru import logger

from .archive_handler import RarBackendUnavailableError, open_archive

JAR = ".jar"


def unpack_mods(
    mods_path: Path,
    temp_path: Path,
    selected_mods: list[str] | None = None,
) -> list[str]:
    mod_list = sorted(
        [m.name for m in mods_path.iterdir() if m.name.endswith(JAR)],
        key=lambda n: n.lower(),
    )

    if selected_mods is not None:
        selected_set = set(selected_mods)
        mod_list = [m for m in mod_list if m in selected_set]

    logger.info(f"Unpacking {len(mod_list)} mod(s)...")

    for mod_name in mod_list:
        mod_file_path = mods_path / mod_name
        unpacking_destination = temp_path / mod_name
        try:
            with open_archive(str(mod_file_path)) as archive:
                logger.info(f"Unpacking {mod_name}...")
                archive.extractall(str(unpacking_destination))
        except RarBackendUnavailableError:
            logger.error(
                "Could not unpack {}: file is a RAR archive but unrar backend "
                "is not available. Install WinRAR / unrar and ensure UnRAR.exe is on PATH "
                "(or set UNRAR_TOOL).",
                mod_name,
            )
            raise
        except (zipfile.BadZipFile, OSError) as exc:
            logger.error("Could not unpack {}: {}", mod_name, exc)
            raise

    return mod_list
