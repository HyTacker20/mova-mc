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

    Concrete implementations (e.g. ProgressReporter, test doubles) need
    only implement ``report(event, **data)``.  Typed convenience methods
    (report_title, report_mod_start, etc.) live on ProgressReporter
    but are not part of this protocol.
    """

    def report(self, event: str, **data: Any) -> None: ...
