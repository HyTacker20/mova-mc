from __future__ import annotations

import json
import os
import zipfile
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

from loguru import logger

from ...domain.languages import LANGUAGE_NAMES

JAR = ".jar"
JSON = ".json"
LANG = ".lang"


def convert_translated_mods(
    temp_path: Path,
    translation_path: Path,
    mods_path: Path,
    target_lang: str = "",
    source_lang: str = "",
    mod_names: list[str] | None = None,
) -> list[str]:
    all_folders = [p.name for p in temp_path.iterdir() if p.is_dir()]
    if mod_names is not None:
        mod_folder_list = []
        for name in mod_names:
            if name in all_folders:
                mod_folder_list.append(name)
            else:
                logger.warning(f"Requested mod '{name}' has no workspace folder — skipping")
    else:
        mod_folder_list = all_folders

    same_paths = mods_path.resolve() == translation_path.resolve()
    if same_paths:
        logger.warning(
            "Output mode is 'replace' — translated JARs will OVERWRITE original mod JARs in {}",
            mods_path,
        )

    for mod_folder in mod_folder_list:
        logger.info(f"Converting {mod_folder} into mod file...")
        unacked_mod_path = temp_path / mod_folder

        dest_path = (mods_path if same_paths else translation_path) / mod_folder

        _convert_folder_to_jar(unacked_mod_path, dest_path, target_lang=target_lang, source_lang=source_lang)

    return mod_folder_list


def _update_pack_mcmeta(folder_path: Path, target_lang: str) -> None:
    """Add target_lang to pack.mcmeta language whitelist so Forge picks it up."""
    mcmeta_path = folder_path / "pack.mcmeta"
    if not mcmeta_path.exists():
        return

    try:
        with mcmeta_path.open("r", encoding="utf-8") as f:
            mcmeta: dict = json.load(f)

        if "language" not in mcmeta:
            return

        full_name = LANGUAGE_NAMES.get(target_lang, target_lang)
        lang_name = full_name.split(" (")[0] if " (" in full_name else full_name
        region = target_lang.split("_")[-1].upper() if "_" in target_lang else ""

        mcmeta["language"][target_lang] = {"name": lang_name, "region": region}

        with mcmeta_path.open("w", encoding="utf-8") as f:
            json.dump(mcmeta, f, indent=4, ensure_ascii=False)

        logger.info(f"Updated pack.mcmeta: added {target_lang} ({lang_name})")
    except (OSError, json.JSONDecodeError) as e:
        logger.warning(f"Could not update pack.mcmeta: {e}")


def _convert_folder_to_jar(
    folder_path: Path,
    jar_path: Path,
    target_lang: str = "",
    source_lang: str = "",
) -> None:
    logger.info(f"Creating JAR file: {jar_path}")
    jar_path.parent.mkdir(parents=True, exist_ok=True)

    if target_lang:
        _update_pack_mcmeta(folder_path, target_lang)

    lang_files_found = []
    for root, _dirs, files in os.walk(str(folder_path)):
        for file in files:
            has_lang_ext = file.lower().endswith(JSON) or file.lower().endswith(LANG)
            if has_lang_ext and target_lang.lower() in file.lower():
                relative_path = os.path.relpath(Path(root) / file, str(folder_path))
                lang_files_found.append(relative_path)
                logger.debug(f"Found target language file: {relative_path}")

    if not lang_files_found:
        logger.warning(f"No target language files found in {folder_path}.")

    file_count = 0
    tmp_jar_path = jar_path.with_suffix(jar_path.suffix + ".tmp")
    try:
        with ZipFile(str(tmp_jar_path), "w", ZIP_DEFLATED) as jar_file:
            for root, _dirs, files in os.walk(str(folder_path)):
                for file in files:
                    file_path = Path(root) / file
                    relative_path = str(os.path.relpath(str(file_path), str(folder_path)))
                    jar_file.write(str(file_path), relative_path)
                    file_count += 1

                    has_lang_ext = file.lower().endswith(JSON) or file.lower().endswith(LANG)
                    if has_lang_ext and target_lang.lower() in file.lower():
                        logger.debug(f"Added target language file to JAR: {relative_path}")

        if tmp_jar_path.exists():
            if zipfile.is_zipfile(str(tmp_jar_path)):
                if jar_path.exists():
                    jar_path.unlink()
                tmp_jar_path.rename(jar_path)
                jar_size = jar_path.stat().st_size
                logger.info(f"Successfully created JAR file with {file_count} files ({jar_size} bytes)")
            else:
                logger.error(f"Temp JAR is not valid: {tmp_jar_path}")
                tmp_jar_path.unlink()
        else:
            logger.error(f"Failed to create JAR file {jar_path}")
    except OSError as e:
        logger.error(f"ERROR creating JAR file: {e}")
