from __future__ import annotations

from pathlib import Path

from loguru import logger

from ...domain.models import LangFile, Mod, TranslationUnit
from ...domain.placeholders import extract_placeholders
from ...infrastructure.parsers import json_parser, lang_parser, mcfunction_parser
from ...utils.cancellation import cancel_token
from ..pipeline import PipelineContext


def stage_parse_sources(_ctx: PipelineContext, mods: list[Mod]) -> list[Mod]:
    """Parse discovered language files into translatable units.

    Reads each LangFile's source file and produces TranslationUnit objects
    with pre-extracted placeholders (%s, {0}, §c). If a hint-language file
    was discovered during the discover stage, also reads it and attaches
    hint_text to the appropriate units.
    """
    result: list[Mod] = []
    for mod in mods:
        if not mod.selected:
            result.append(mod)
            continue

        cancel_token.raise_if_set()

        # Load hint-language data if available
        hint_data: dict[str, str] = {}
        hint_path: Path | None = getattr(mod, "_hint_path", None)
        if hint_path and hint_path.exists():
            hint_data = _load_hint_file(hint_path)

        parsed_files: list[LangFile] = []
        for lang_file in mod.lang_files:
            units = _parse_file_into_units(lang_file, hint_data=hint_data)
            if units is not None:
                parsed_files.append(
                    LangFile(
                        mod_name=lang_file.mod_name,
                        source_path=lang_file.source_path,
                        target_path=lang_file.target_path,
                        file_type=lang_file.file_type,
                        units=units,
                    )
                )

        total_units = sum(len(f.units) for f in parsed_files)
        if parsed_files:
            logger.info(f"Parsed {total_units} unit(s) from {len(parsed_files)} file(s) for {mod.name}")
        else:
            logger.info(f"No files to parse for {mod.name} — skipping")

        result_mod = Mod(
            name=mod.name,
            path=mod.path,
            lang_files=tuple(parsed_files),
            selected=mod.selected,
        )
        # Propagate ephemeral attributes set by prior stages
        # (e.g. _effective_source_lang from discover fallback)
        effective_source = getattr(mod, "_effective_source_lang", None)
        if effective_source:
            object.__setattr__(result_mod, "_effective_source_lang", effective_source)

        result.append(result_mod)

    return result


def _load_hint_file(path: Path) -> dict[str, str]:
    """Read a hint-language file (JSON or LANG) and return key→value pairs."""
    try:
        ext = path.suffix.lower()
        if ext == ".json":
            return json_parser.parse_json_with_comments(path)
        if ext == ".lang":
            return lang_parser.read_lang_file(path)
        return {}
    except Exception:
        logger.debug(f"Could not parse hint file {path}, ignoring")
        return {}


def _parse_file_into_units(
    lang_file: LangFile,
    hint_data: dict[str, str] | None = None,
) -> tuple[TranslationUnit, ...] | None:
    try:
        if lang_file.file_type == "json":
            data = json_parser.parse_json_with_comments(lang_file.source_path)
        elif lang_file.file_type == "lang":
            data = lang_parser.read_lang_file(lang_file.source_path)
        elif lang_file.file_type == "mcfunction":
            data = mcfunction_parser.read_mcfunction_file(lang_file.source_path)
        else:
            return None

        if not data:
            return None

        units: list[TranslationUnit] = []
        for k, v in data.items():
            hint = hint_data.get(k) if hint_data else None
            units.append(
                TranslationUnit(
                    key=k,
                    source_text=v,
                    file_type=lang_file.file_type,
                    placeholders=extract_placeholders(v),
                    hint_text=hint,
                )
            )
        return tuple(units)
    except Exception:
        logger.exception(f"Failed to parse {lang_file.source_path}")
        return None
