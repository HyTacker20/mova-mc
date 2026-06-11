from __future__ import annotations

import os
from pathlib import Path

from loguru import logger

JAR = ".jar"
JSON = ".json"
LANG = ".lang"
MCFUNCTION = ".mcfunction"


def discover_lang_files(temp_path: Path, source_lang: str) -> list[str]:
    lang_folders: list[str] = []
    found_files: list[tuple[str, str]] = []

    logger.info(f"Searching for language files in {temp_path}...")

    source_json_lower = f"{source_lang.lower()}{JSON}"
    source_json_original = f"{source_lang}{JSON}"
    source_lang_lower = f"{source_lang.lower()}{LANG}"
    source_lang_original = f"{source_lang}{LANG}"

    for foldername, _dirnames, filenames in os.walk(str(temp_path)):
        for filename in filenames:
            lower_filename = filename.lower()
            if lower_filename in (source_json_lower.lower(), source_json_original.lower()) or lower_filename in (
                source_lang_lower.lower(),
                source_lang_original.lower(),
            ):
                found_files.append((foldername, filename))

    for folder, filename in found_files:
        if "lang" in folder.lower():
            if folder not in lang_folders:
                lang_folders.append(folder)
                mod_path_parts = Path(folder).parts
                mod_name = mod_path_parts[1] if len(mod_path_parts) > 1 else "unknown"
                logger.debug(f"Found language folder: {folder} (mod: {mod_name})")
                logger.debug(f"Contains source file: {filename}")
        else:
            parent_folder = str(Path(folder).parent)
            if parent_folder not in lang_folders:
                lang_folders.append(parent_folder)
                mod_path_parts = Path(parent_folder).parts
                mod_name = mod_path_parts[1] if len(mod_path_parts) > 1 else "unknown"
                logger.debug(f"Found language file outside standard lang folder: {folder} ({mod_name})")
                logger.debug(f"Using parent folder: {parent_folder}")

    mcfunction_folders = _discover_mcfunction_folders(temp_path)
    for folder in mcfunction_folders:
        if folder not in lang_folders:
            lang_folders.append(folder)

    if not lang_folders:
        logger.info(f"Warning: No language folders found containing {source_lang} files")
        for dirpath, _dirnames, _filenames in os.walk(str(temp_path)):
            if "lang" in dirpath.lower() or "assets" in dirpath.lower():
                logger.info(f"  - {dirpath}")
                logger.info(f"    Contents: {list(Path(dirpath).iterdir())}")

    return lang_folders


def _discover_mcfunction_folders(temp_path: Path) -> list[str]:
    mcfunction_folders: list[str] = []
    logger.debug(f"Searching for .mcfunction files in {temp_path}...")

    for foldername, _dirnames, filenames in os.walk(str(temp_path)):
        for filename in filenames:
            if filename.endswith(MCFUNCTION):
                path_parts = Path(foldername).parts
                temp_parts = temp_path.parts

                if len(path_parts) > len(temp_parts):
                    mod_root_parts = [*temp_parts, path_parts[len(temp_parts)]]
                    mod_root = str(Path(*mod_root_parts))

                    if mod_root not in mcfunction_folders:
                        mcfunction_folders.append(mod_root)
                        mod_name = path_parts[len(temp_parts)] if len(path_parts) > len(temp_parts) else "unknown"
                        logger.debug(f"Found mod with .mcfunction files: {mod_name}")
                        break

    return mcfunction_folders
