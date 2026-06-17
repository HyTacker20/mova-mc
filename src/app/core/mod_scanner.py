from __future__ import annotations

import fnmatch
import json
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..domain.models import Mod

from loguru import logger

from ..infrastructure.filesystem.archive_handler import RarBackendUnavailableError, open_archive
from ..utils.progress import ProgressReporter

JAR = ".jar"
JSON = ".json"
LANG = ".lang"
MCFUNCTION = ".mcfunction"


@dataclass
class ModInfo:
    jar_path: Path
    name: str
    size_bytes: int
    has_lang_files: bool
    lang_file_count: int
    mcfunction_count: int
    estimated_entries: int
    source_files: list[str] = field(default_factory=list)
    selected: bool = False
    namespaces: list[str] = field(default_factory=list)
    in_resource_pack: bool = False


def _count_entries_from_json(raw: str) -> int:
    try:
        data = json.loads(raw)
        if isinstance(data, dict):
            return len(data)
    except (json.JSONDecodeError, TypeError):
        pass
    return 0


def _extract_namespace(name: str) -> str | None:
    """Extract namespace from a path like ``assets/minecraft/lang/en_US.json``.

    Returns the namespace component (e.g. ``"minecraft"``) or ``None`` if the
    path doesn't follow the expected ``assets/<ns>/lang/...`` layout.
    """
    parts = name.replace("\\", "/").split("/")
    try:
        idx = parts.index("assets")
        if idx + 2 < len(parts) and parts[idx + 2] == "lang":
            return parts[idx + 1]
    except ValueError:
        pass
    return None


def _count_entries_from_lang(raw: str) -> int:
    count = 0
    for line in raw.splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            count += 1
    return count


def modinfo_to_domain_mod(mod_info: ModInfo) -> Mod:
    """Convert a ModInfo to a domain Mod model.

    Attaches ``_estimated_entries`` as a non-public attribute so the
    pipeline can pre-compute a global entry count before unpacking.
    """
    from ..domain.models import Mod

    mod = Mod(
        name=mod_info.name,
        path=mod_info.jar_path,
        selected=mod_info.selected,
    )
    object.__setattr__(mod, "_estimated_entries", mod_info.estimated_entries)
    return mod


def _is_source_lang_file(filename: str, source_lang: str) -> bool:
    """Check if *filename* (basename, e.g. ``en_US.json``) matches *source_lang*.

    Case-insensitive matching so ``en_US``, ``En_Us``, and ``en_us`` all
    match the file ``en_us.json``.
    """
    stem = filename.rsplit(".", 1)[0] if "." in filename else filename
    return stem.lower() == source_lang.lower()


class ModScanner:
    def __init__(
        self,
        mods_path: str,
        reporter: ProgressReporter | None = None,
        source_lang: str | None = None,
    ) -> None:
        self.mods_path = Path(mods_path)
        self.reporter = reporter or ProgressReporter()
        self.source_lang = source_lang

    def discover_mods(self, include: list[str] | None = None, exclude: list[str] | None = None) -> list[ModInfo]:
        if include is None:
            include = ["*"]
        if exclude is None:
            exclude = []

        jar_paths = sorted(
            [p for p in self.mods_path.iterdir() if p.suffix == JAR and p.is_file()],
            key=lambda p: p.name.lower(),
        )

        self.reporter.report_scan_start(len(jar_paths))

        mods: list[ModInfo] = []
        for idx, jar_path in enumerate(jar_paths):
            self.reporter.report_scan_progress(idx + 1, len(jar_paths), jar_path.name)
            mod_info = self._scan_jar(jar_path)

            if not self._matches_filters(mod_info.name, include, exclude):
                mod_info.selected = False

            mods.append(mod_info)

        self.reporter.report_scan_complete(len(mods))
        return mods

    def _scan_jar(self, jar_path: Path) -> ModInfo:
        size_bytes = jar_path.stat().st_size
        source_files: list[str] = []
        lang_file_count = 0
        mcfunction_count = 0
        estimated_entries = 0
        has_lang_files = False
        namespaces: set[str] = set()

        # Collect ALL lang files first, then decide which to count.
        all_lang_files: list[tuple[str, str]] = []  # (name, raw_content)
        all_mcfunction_files: list[str] = []

        try:
            with open_archive(jar_path) as archive:
                for name in archive.namelist():
                    lower = name.lower()
                    if lower.endswith(JSON) or lower.endswith(LANG):
                        basename = name.rsplit("/", 1)[-1] if "/" in name else name
                        try:
                            raw = archive.read(name).decode("utf-8", errors="replace")
                        except Exception:
                            raw = ""
                        all_lang_files.append((basename, raw))
                        # Extract namespace from path
                        ns = _extract_namespace(name)
                        if ns:
                            namespaces.add(ns)
                    elif lower.endswith(MCFUNCTION):
                        all_mcfunction_files.append(name)

        except RarBackendUnavailableError:
            logger.warning(
                "Could not scan JAR {}: file is a RAR archive but unrar backend "
                "is not available. Install WinRAR / unrar and ensure UnRAR.exe is on PATH "
                "(or set UNRAR_TOOL).",
                jar_path.name,
            )
        except (zipfile.BadZipFile, OSError) as e:
            logger.warning(f"Could not scan JAR {jar_path.name}: {e}")

        # ── Count entries: prefer source_lang, fall back to en_US ──
        source_matches: list[tuple[str, str]] = []
        en_fallback: list[tuple[str, str]] = []
        other_files: list[tuple[str, str]] = []

        for basename, raw in all_lang_files:
            if self.source_lang and _is_source_lang_file(basename, self.source_lang):
                source_matches.append((basename, raw))
            elif basename.lower().startswith("en_"):
                en_fallback.append((basename, raw))
            else:
                other_files.append((basename, raw))

        # When source_lang is set: prefer matching files, fall back to English.
        # When source_lang is None: count all files.
        if self.source_lang:
            counted = source_matches if source_matches else en_fallback
        else:
            counted = source_matches + en_fallback + other_files

        for basename, raw in counted:
            source_files.append(basename)
            lang_file_count += 1
            has_lang_files = True
            lower = basename.lower()
            if lower.endswith(JSON):
                estimated_entries += _count_entries_from_json(raw)
            elif lower.endswith(LANG):
                estimated_entries += _count_entries_from_lang(raw)

        # MCFUNCTION files don't have a language code — always include them.
        mcfunction_count = len(all_mcfunction_files)
        if mcfunction_count > 0:
            has_lang_files = True
            source_files.extend(all_mcfunction_files)

        return ModInfo(
            jar_path=jar_path,
            name=jar_path.name,
            size_bytes=size_bytes,
            has_lang_files=has_lang_files,
            lang_file_count=lang_file_count,
            mcfunction_count=mcfunction_count,
            estimated_entries=estimated_entries,
            source_files=source_files,
            selected=has_lang_files,
            namespaces=sorted(namespaces),
        )

    @staticmethod
    def _matches_filters(name: str, include: list[str], exclude: list[str]) -> bool:
        for pattern in exclude:
            if fnmatch.fnmatch(name, pattern):
                return False
        return any(fnmatch.fnmatch(name, pattern) for pattern in include)


def check_resource_pack_mods(
    mods: list[ModInfo],
    output_dir: str,
    target_lang: str,
    pack_name: str,
) -> None:
    """Mark *mods* whose namespaces are found in an existing resource pack zip.

    Reads ``<output_dir>/<pack_name>.zip`` and sets
    ``mod.in_resource_pack = True`` for any mod whose namespaces all appear
    inside the pack.
    """
    pack_path = Path(output_dir) / f"{pack_name}.zip"
    if not pack_path.is_file():
        logger.debug("No existing resource pack at {}", pack_path)
        return

    pack_namespaces: set[str] = set()
    try:
        with zipfile.ZipFile(pack_path, "r") as zf:
            target_lang_lower = target_lang.lower()
            for name in zf.namelist():
                # Entries like assets/<ns>/lang/<target_lang>.json
                lower = name.lower()
                if not lower.endswith((".json", ".lang")):
                    continue
                # Check if this is a target-language file
                stem = Path(name).stem.lower()
                if stem != target_lang_lower:
                    continue
                ns = _extract_namespace(name)
                if ns:
                    pack_namespaces.add(ns)
    except (zipfile.BadZipFile, OSError) as exc:
        logger.warning("Could not read resource pack {}: {}", pack_path, exc)
        return

    if not pack_namespaces:
        logger.debug("Resource pack at {} contains no target-lang entries for {}", pack_path, target_lang)
        return

    logger.info(
        "Found {} namespace(s) in existing resource pack: {}",
        len(pack_namespaces),
        ", ".join(sorted(pack_namespaces)),
    )

    for mod in mods:
        if not mod.namespaces:
            continue
        # A mod is "in the pack" if at least one of its namespaces is present.
        if any(ns in pack_namespaces for ns in mod.namespaces):
            mod.in_resource_pack = True
