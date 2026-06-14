from __future__ import annotations

import time
from dataclasses import dataclass, field


@dataclass
class FileStats:
    path: str
    file_type: str
    entries_total: int = 0
    entries_translated: int = 0
    entries_failed: int = 0
    start_time: float = 0.0
    duration_ms: int = 0

    def start(self) -> None:
        self.start_time = time.monotonic()

    def finish(self) -> None:
        self.duration_ms = int((time.monotonic() - self.start_time) * 1000)

    def add_translated(self, count: int) -> None:
        self.entries_translated += count

    def add_failed(self, count: int) -> None:
        self.entries_failed += count


@dataclass
class ModStats:
    name: str
    files: list[FileStats] = field(default_factory=list)
    total_entries: int = 0
    translated_entries: int = 0
    failed_entries: int = 0
    start_time: float = 0.0
    duration_ms: int = 0
    skipped: bool = False

    def start(self) -> None:
        self.start_time = time.monotonic()

    def finish(self) -> None:
        self.duration_ms = int((time.monotonic() - self.start_time) * 1000)
        self.total_entries = sum(f.entries_total for f in self.files)
        self.translated_entries = sum(f.entries_translated for f in self.files)
        self.failed_entries = sum(f.entries_failed for f in self.files)


@dataclass
class OverallStats:
    mods: list[ModStats] = field(default_factory=list)
    total_mods: int = 0
    translated_mods: int = 0
    skipped_mods: int = 0
    total_entries: int = 0
    translated_entries: int = 0
    failed_entries: int = 0
    total_duration_ms: int = 0
    provider: str = ""
    source_lang: str = ""
    target_lang: str = ""
    start_time: float = 0.0
    # QA metrics
    qa_enabled: bool = False
    qa_judged: int = 0
    qa_flagged: int = 0
    qa_corrected: int = 0
    qa_warnings: int = 0

    def start(self) -> None:
        self.start_time = time.monotonic()

    def finish(self) -> None:
        self.total_duration_ms = int((time.monotonic() - self.start_time) * 1000)
        self.total_mods = len(self.mods)
        self.translated_mods = sum(1 for m in self.mods if not m.skipped)
        self.skipped_mods = sum(1 for m in self.mods if m.skipped)
        self.total_entries = sum(m.total_entries for m in self.mods)
        self.translated_entries = sum(m.translated_entries for m in self.mods)
        self.failed_entries = sum(m.failed_entries for m in self.mods)

    def to_dict(self) -> dict:
        return {
            "total_mods": self.total_mods,
            "translated_mods": self.translated_mods,
            "skipped_mods": self.skipped_mods,
            "total_entries": self.total_entries,
            "translated_entries": self.translated_entries,
            "failed_entries": self.failed_entries,
            "total_duration_ms": self.total_duration_ms,
            "provider": self.provider,
            "source_lang": self.source_lang,
            "target_lang": self.target_lang,
            "qa_enabled": self.qa_enabled,
            "qa_judged": self.qa_judged,
            "qa_flagged": self.qa_flagged,
            "qa_corrected": self.qa_corrected,
            "qa_warnings": self.qa_warnings,
            "mods": [
                {
                    "name": m.name,
                    "skipped": m.skipped,
                    "total_entries": m.total_entries,
                    "translated_entries": m.translated_entries,
                    "failed_entries": m.failed_entries,
                    "duration_ms": m.duration_ms,
                    "files": [
                        {
                            "path": f.path,
                            "file_type": f.file_type,
                            "entries_total": f.entries_total,
                            "entries_translated": f.entries_translated,
                            "entries_failed": f.entries_failed,
                            "duration_ms": f.duration_ms,
                        }
                        for f in m.files
                    ],
                }
                for m in self.mods
            ],
        }
