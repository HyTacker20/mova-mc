from __future__ import annotations

import os
from pathlib import Path

from loguru import logger

from ...domain.models import LangFile, Mod
from ...utils.cancellation import cancel_token
from ..pipeline import PipelineContext

JSON = ".json"
LANG = ".lang"
MCFUNCTION = ".mcfunction"


def _detect_lang_casing(directory: Path, extension: str, target_lang: str) -> str:
    """Detect casing pattern from existing language files and apply it to target_lang.

    Scans *directory* for files matching *extension* (e.g. ``.lang``), extracts
    the casing pattern of the language + region parts from each, and applies
    the most common pattern to *target_lang*.

    Examples
    --------
    Directory has ``en_US.lang``, ``ru_RU.lang``
        → ``_detect_lang_casing(dir, ".lang", "uk_UA")`` → ``"uk_UA"``

    Directory has ``en_us.json``
        → ``_detect_lang_casing(dir, ".json", "uk_UA")`` → ``"uk_ua"``

    Directory has ``EN_us.lang``
        → ``_detect_lang_casing(dir, ".lang", "uk_UA")`` → ``"UK_ua"``

    No existing files → fallback to all-lowercase (Minecraft JSON convention).
    """
    target_parts = target_lang.split("_")
    if len(target_parts) < 2:
        return target_lang.lower()

    target_lang_part = target_parts[0]
    target_region_part = "_".join(target_parts[1:])

    # Determine region case: already uppercased by Settings._format_lang → use as vote for "upper"
    # Default vote: if target already has uppercase region, we prefer uppercase
    pattern_counts: dict[str, int] = {}

    if directory.exists():
        for f in directory.glob(f"*{extension}"):
            stem = f.stem
            if "_" in stem:
                parts = stem.split("_")
                lang_part = parts[0]
                region_part = "_".join(parts[1:])

                lang_case = "upper" if lang_part.isupper() else "lower" if lang_part.islower() else "mixed"
                region_case = "upper" if region_part.isupper() else "lower" if region_part.islower() else "mixed"
                key = f"{lang_case}_{region_case}"
                pattern_counts[key] = pattern_counts.get(key, 0) + 1

    if not pattern_counts:
        return target_lang.lower()

    most_common = max(pattern_counts, key=lambda k: pattern_counts[k])
    lang_case, region_case = most_common.split("_")

    if lang_case == "upper":
        target_lang_part = target_lang_part.upper()
    elif lang_case == "lower":
        target_lang_part = target_lang_part.lower()

    if region_case == "upper":
        target_region_part = target_region_part.upper()
    elif region_case == "lower":
        target_region_part = target_region_part.lower()

    return f"{target_lang_part}_{target_region_part}"


def _is_source_file(lower: str, lang: str, ext: str) -> bool:
    """Check if a lowercased filename matches a source language file pattern.

    Matches both lowercased and original-casing variants of the language code
    against the lowercased filename so that e.g. ``en_US``, ``En_Us``, and
    ``en_us`` all match the file ``en_us.json``.
    """
    return lower in (f"{lang.lower()}{ext}", f"{lang}{ext}")


def stage_discover_files(ctx: PipelineContext, mods: list[Mod]) -> list[Mod]:
    """Walk each mod's unpacked directory to find all translatable source files
    and (optionally) a hint-language file.

    Produces LangFile entries with source_path and target_path set but empty
    units — the parse stage fills in the text. Handles JSON, LANG, and
    MCFUNCTION file types.

    If ``ctx.settings.hint_lang`` is set, also looks for a matching file
    to use as translation hint context (stored via :class:`HintContext`).

    If no files match the configured source language, falls back to ``en_US``
    so that English-language mods are still translated even when the primary
    source is a different language.
    """
    source_lang = ctx.settings.source_mc_lang
    target_lang = ctx.settings.target_mc_lang
    hint_lang = ctx.settings.hint_lang
    workspace = ctx.workspace

    # Fallback to English when the configured source language is not found.
    # This handles mods that only ship English translations.
    fallback_lang = "en_US"
    may_fallback = source_lang.lower() != fallback_lang.lower()

    result: list[Mod] = []
    for mod in mods:
        if not mod.selected:
            result.append(mod)
            continue

        cancel_token.raise_if_set()

        mod_dir = workspace / mod.name
        if not mod_dir.exists():
            logger.warning(f"Mod directory not found: {mod_dir}")
            result.append(mod)
            continue

        primary_files: list[LangFile] = []
        fallback_files: list[LangFile] = []
        mcfunction_files: list[LangFile] = []
        hint_path: Path | None = None

        for root, _dirs, files in os.walk(str(mod_dir)):
            root_path = Path(root)
            for filename in files:
                lower = filename.lower()

                # ── 1. Primary source language files ──
                if _is_source_file(lower, source_lang, JSON):
                    formatted_target = _detect_lang_casing(root_path, JSON, target_lang)
                    target_path = root_path / f"{formatted_target}{JSON}"
                    primary_files.append(
                        LangFile(
                            mod_name=mod.name,
                            source_path=root_path / filename,
                            target_path=target_path,
                            file_type="json",
                        )
                    )
                elif _is_source_file(lower, source_lang, LANG):
                    formatted_target = _detect_lang_casing(root_path, LANG, target_lang)
                    target_path = root_path / f"{formatted_target}{LANG}"
                    primary_files.append(
                        LangFile(
                            mod_name=mod.name,
                            source_path=root_path / filename,
                            target_path=target_path,
                            file_type="lang",
                        )
                    )
                # ── 2. Fallback to en_US if no primary found yet ──
                elif may_fallback and not primary_files and _is_source_file(lower, fallback_lang, JSON):
                    formatted_target = _detect_lang_casing(root_path, JSON, target_lang)
                    target_path = root_path / f"{formatted_target}{JSON}"
                    fallback_files.append(
                        LangFile(
                            mod_name=mod.name,
                            source_path=root_path / filename,
                            target_path=target_path,
                            file_type="json",
                        )
                    )
                elif may_fallback and not primary_files and _is_source_file(lower, fallback_lang, LANG):
                    formatted_target = _detect_lang_casing(root_path, LANG, target_lang)
                    target_path = root_path / f"{formatted_target}{LANG}"
                    fallback_files.append(
                        LangFile(
                            mod_name=mod.name,
                            source_path=root_path / filename,
                            target_path=target_path,
                            file_type="lang",
                        )
                    )
                # ── 3. MCFUNCTION files (always included, language-agnostic) ──
                elif filename.endswith(MCFUNCTION):
                    mcfunction_files.append(
                        LangFile(
                            mod_name=mod.name,
                            source_path=root_path / filename,
                            target_path=root_path / filename,
                            file_type="mcfunction",
                        )
                    )

                # ── 4. Hint-language file discovery (always, regardless of source) ──
                if hint_lang:
                    hint_lower = hint_lang.lower()
                    if lower in (f"{hint_lower}{JSON}", f"{hint_lang}{JSON}") or lower in (
                        f"{hint_lower}{LANG}",
                        f"{hint_lang}{LANG}",
                    ):
                        hint_path = root_path / filename

        # ── Determine effective source language ──
        if primary_files:
            effective_source = source_lang
            lang_files = primary_files + mcfunction_files
            log_msg = f"Discovered {len(lang_files)} source file(s) for {mod.name}"
        elif fallback_files:
            effective_source = fallback_lang
            lang_files = fallback_files + mcfunction_files
            log_msg = (
                f"No {source_lang} files for {mod.name}"
                f" — fell back to {fallback_lang} ({len(lang_files)} file(s))"
            )
        else:
            effective_source = source_lang
            lang_files = []
            log_msg = f"No source language files found for {mod.name} — skipping"

        # Attach hint path and fallback info to mod's metadata
        # via non-public attributes (same pattern as _inject_hint_path).
        mod_with_hint = Mod(
            name=mod.name,
            path=mod.path,
            lang_files=tuple(lang_files),
            selected=mod.selected,
        )
        if hint_path:
            mod_with_hint = _inject_hint_path(mod_with_hint, hint_path)
        if effective_source != source_lang:
            object.__setattr__(mod_with_hint, "_effective_source_lang", effective_source)

        logger.info(log_msg)
        result.append(mod_with_hint)

    return result


def _inject_hint_path(mod: Mod, hint_path: Path) -> Mod:
    """Store the hint-language file path on the mod without modifying the
    frozen dataclass interface — uses a non-public attribute."""
    object.__setattr__(mod, "_hint_path", hint_path)
    return mod
