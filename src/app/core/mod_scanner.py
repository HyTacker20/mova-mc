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


def _count_entries_from_json(raw: str) -> int:
    try:
        data = json.loads(raw)
        if isinstance(data, dict):
            return len(data)
    except (json.JSONDecodeError, TypeError):
        pass
    return 0


def _count_entries_from_lang(raw: str) -> int:
    count = 0
    for line in raw.splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            count += 1
    return count


def modinfo_to_domain_mod(mod_info: ModInfo) -> Mod:
    """Convert a ModInfo to a domain Mod model."""
    from ..domain.models import Mod

    return Mod(
        name=mod_info.name,
        path=mod_info.jar_path,
        selected=mod_info.selected,
    )


class ModScanner:
    def __init__(self, mods_path: str, reporter: ProgressReporter | None = None) -> None:
        self.mods_path = Path(mods_path)
        self.reporter = reporter or ProgressReporter()

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

        try:
            with open_archive(jar_path) as archive:
                for name in archive.namelist():
                    lower = name.lower()
                    if lower.endswith(JSON) or lower.endswith(LANG):
                        source_files.append(name)
                        lang_file_count += 1
                        has_lang_files = True
                        if estimated_entries == 0:
                            try:
                                raw = archive.read(name).decode("utf-8", errors="replace")
                                if lower.endswith(JSON):
                                    estimated_entries = _count_entries_from_json(raw)
                                elif lower.endswith(LANG):
                                    estimated_entries = _count_entries_from_lang(raw)
                            except Exception:
                                logger.debug(f"Could not parse entries from {name}")
                    elif lower.endswith(MCFUNCTION):
                        mcfunction_count += 1
                        source_files.append(name)
                        has_lang_files = True
        except RarBackendUnavailableError:
            logger.warning(
                "Could not scan JAR {}: file is a RAR archive but unrar backend "
                "is not available. Install WinRAR / unrar and ensure UnRAR.exe is on PATH "
                "(or set UNRAR_TOOL).",
                jar_path.name,
            )
        except (zipfile.BadZipFile, OSError) as e:
            logger.warning(f"Could not scan JAR {jar_path.name}: {e}")

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
        )

    @staticmethod
    def _matches_filters(name: str, include: list[str], exclude: list[str]) -> bool:
        for pattern in exclude:
            if fnmatch.fnmatch(name, pattern):
                return False
        return any(fnmatch.fnmatch(name, pattern) for pattern in include)
