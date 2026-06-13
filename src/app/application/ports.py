"""Port interfaces (protocols) for the translation pipeline.

These define the boundary between the application layer and infrastructure.
Implementations live in infrastructure/.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, Protocol, runtime_checkable

from ..domain.models import TranslationResult, TranslationUnit


@runtime_checkable
class TranslationProvider(Protocol):
    """Protocol for translation services.

    Each provider must implement translate() for single strings and
    translate_unit() for domain-model-aware translation with error tracking.
    translate_batch_async() handles bulk translation with structured results
    and an optional per-entry callback.

    Async variants (translate_async, translate_unit_async,
    translate_batch_async) are used by the async pipeline.
    """

    def translate(self, text: str) -> str:
        """Translate a single text string. Returns original on failure."""

    def translate_unit(self, unit: TranslationUnit) -> TranslationResult:
        """Translate a TranslationUnit, returning a structured result."""

    async def translate_async(self, text: str) -> str:
        """Async single-text translation. Returns original on failure."""

    async def translate_unit_async(self, unit: TranslationUnit) -> TranslationResult:
        """Async TranslationUnit translation with structured result."""

    async def translate_batch_async(
        self,
        units: list[TranslationUnit],
        *,
        on_entry: Callable[[str, str, str], None] | None = None,
    ) -> list[TranslationResult]:
        """Async batch translation with structured results."""


@runtime_checkable
class TranslationCache(Protocol):
    """Persistent cache for translation results, keyed by content hash."""

    def get(self, key: str) -> str | None: ...
    def set(self, key: str, value: str) -> None: ...


@runtime_checkable
class ProgressSink(Protocol):
    """Event sink for pipeline progress reporting.

    Accepts arbitrary string-keyed events with typed data payloads.
    Subscribers in CLI/TUI layers render progress based on these events.

    Typed convenience methods mirror :class:`ProgressReporter`; concrete
    implementations (e.g. test doubles) must provide the full surface.
    """

    def report(self, event: str, **data: Any) -> None: ...

    # ── Pipeline lifecycle ──────────────────────────────────────────
    def report_title(self, title: str) -> None: ...
    def report_message(self, message: str) -> None: ...
    def report_error(self, error: str) -> None: ...
    def report_complete(self, output_path: str) -> None: ...

    # ── Scan phase ──────────────────────────────────────────────────
    def report_scan_start(self, total: int) -> None: ...
    def report_scan_progress(self, current: int, total: int, name: str) -> None: ...
    def report_scan_complete(self, total: int) -> None: ...

    # ── Per-mod translation ─────────────────────────────────────────
    def report_mod_start(self, mod_name: str, file_count: int, entry_count: int) -> None: ...
    def report_mod_file_start(self, mod_name: str, file_path: str, entry_count: int) -> None: ...
    def report_mod_file_progress(self, mod_name: str, file_path: str, current: int, total: int) -> None: ...
    def report_mod_file_complete(self, mod_name: str, file_path: str, duration_ms: int, errors: int) -> None: ...
    def report_mod_complete(self, mod_name: str, translated: int, total: int, failed: int) -> None: ...

    # ── Overall progress ────────────────────────────────────────────
    def report_overall_progress(
        self,
        completed_mods: int,
        total_mods: int,
        completed_entries: int,
        total_entries: int,
        fractional_mods: float | None = None,
    ) -> None: ...

    # ── Entry-level ─────────────────────────────────────────────────
    def report_progress(self, current: int, total: int, item: str = "") -> None: ...
    def report_entry_progress(self, done: int, total: int, mod_name: str = "", file_path: str = "") -> None: ...
    def report_translated_entry(self, key: str, source: str, translated: str, mod_name: str = "") -> None: ...

    # ── Repack phase ────────────────────────────────────────────────
    def report_repack_start(self, total: int) -> None: ...
    def report_repack_progress(self, current: int, total: int, name: str) -> None: ...
    def report_repack_complete(self, total: int) -> None: ...

    # ── QA phase ────────────────────────────────────────────────────
    def report_qa_progress(self, done: int, total: int) -> None: ...
    def report_qa_start(self, total: int, provider: str, model: str) -> None: ...
    def report_qa_verdict(
        self, key: str, score: int, is_flagged: bool, issue: str | None = None
    ) -> None: ...
    def report_qa_correction(
        self, key: str, accepted: bool, attempt: int, max_attempts: int
    ) -> None: ...
    def report_qa_done(self, flagged: int, corrected: int) -> None: ...
    def report_qa_warning(self, key: str, message: str) -> None: ...
