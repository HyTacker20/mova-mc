from __future__ import annotations

import json
from pathlib import Path

from loguru import logger

from ...domain.models import LangFile, Mod, TranslationResult, TranslationUnit
from ...infrastructure.parsers import lang_parser, mcfunction_parser
from ...utils.cancellation import cancel_token
from ..pipeline import PipelineContext


def stage_write_targets(_ctx: PipelineContext, mods: list[Mod]) -> list[Mod]:
    """Write translated entries to target language files on disk.

    Creates target files (e.g., uk_ua.json) alongside source files with
    translated content. Handles JSON, LANG, and MCFUNCTION output formats.
    """
    for mod in mods:
        if not mod.selected:
            continue

        cancel_token.raise_if_set()

        if not mod.lang_files:
            logger.info(f"No target files to write for {mod.name} — skipping")
            continue

        written = 0
        for lang_file in mod.lang_files:
            data = _units_to_dict(lang_file)
            if not data:
                continue
            if lang_file.file_type == "json":
                _write_json_target(lang_file.target_path, data)
            elif lang_file.file_type == "lang":
                _write_lang_target(lang_file.target_path, data)
            elif lang_file.file_type == "mcfunction":
                _write_mcfunction_target(lang_file.target_path, data)
            written += 1

        logger.info(f"Wrote {written} target file(s) for {mod.name}")

    return mods


def _units_to_dict(lang_file: LangFile) -> dict[str, str]:
    data: dict[str, str] = {}
    for unit in lang_file.units:
        if isinstance(unit, TranslationResult):
            data[unit.unit.key] = unit.translated_text
        elif isinstance(unit, TranslationUnit):
            data[unit.key] = unit.source_text
    return data


def _write_json_target(path: Path, data: dict[str, str]) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    newline = _detect_newline(path)
    content = json.dumps(data, indent=4, ensure_ascii=False)
    with path.open("w", encoding="utf-8", newline=newline) as fh:
        fh.write(content)
    logger.info(f"Wrote JSON target: {path}")


def _detect_newline(path: Path) -> str:
    """Return the line ending used by an existing file, defaulting to LF."""
    if not path.exists():
        return "\n"
    try:
        with path.open("rb") as fh:
            sample = fh.read(8192)
    except OSError:
        return "\n"
    return "\r\n" if b"\r\n" in sample else "\n"


def _write_lang_target(path: Path, data: dict[str, str]) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    lang_parser.write_lang_file(data, path)
    logger.info(f"Wrote LANG target: {path}")


def _write_mcfunction_target(path: Path, data: dict[str, str]) -> None:
    path = Path(path)
    mcfunction_parser.write_mcfunction_file(path, data)
    logger.info(f"Wrote MCFUNCTION target: {path}")
