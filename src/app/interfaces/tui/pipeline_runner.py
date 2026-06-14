"""Pipeline runner — thin TUI adapter over TranslationJob.

Bridges TranslationJob progress events and lifecycle callbacks from worker
threads to the Textual message bus, and manages the loguru→TUI log sink.

The runner accepts callbacks instead of reaching into ``TranslateRunStep``
widgets directly, so it can be tested independently of the TUI.
"""

from __future__ import annotations

import asyncio
import contextlib
import time
from collections.abc import Callable
from typing import Any

from loguru import logger

from ...application.job import JobStatus, TranslationJob
from ...core.mod_scanner import ModInfo
from ...core.settings import Settings
from ...domain.stats import OverallStats
from ...logging_config import add_callback_sink
from ...utils.progress import ProgressReporter


class PipelineRunner:
    """Thin TUI adapter over TranslationJob.

    Wires the job's ProgressReporter to Textual callbacks and manages
    the loguru→TUI log sink. The TUI wizard creates one instance per run.

    Parameters
    ----------
    settings:
        Resolved translation settings.
    selected_mods:
        Mods chosen by the user (``ModInfo`` list from the scanner).
    on_progress:
        Called from **any thread** with ``(event_name, data_dict)``.
        The callee is responsible for thread-safety (e.g. ``post_message``).
    on_log:
        Called with a single Rich-markup ``str`` line from **any thread**.
    on_done:
        Called on the asyncio event loop with the final ``OverallStats``.
    on_error:
        Called on the asyncio event loop with an error message ``str``.
    """

    def __init__(
        self,
        settings: Settings,
        selected_mods: list[ModInfo],
        *,
        on_progress: Callable[[str, dict[str, Any]], None],
        on_log: Callable[[str], None],
        on_done: Callable[[OverallStats], None],
        on_error: Callable[[str], None],
        is_debug: bool = False,
    ) -> None:
        self._on_progress = on_progress
        self._on_log = on_log
        self._on_done = on_done
        self._on_error = on_error
        self._is_debug = is_debug

        self._job = TranslationJob(settings=settings, selected_mods=selected_mods)
        self._job.reporter.subscribe(self._bridge_progress)

        self._log_sink_id: int | None = None
        self._start_time: float = 0.0

    # -- public API ----------------------------------------------------

    @property
    def reporter(self) -> ProgressReporter:
        """The progress reporter feeding events to ``on_progress``."""
        return self._job.reporter

    def start(self) -> None:
        """Validate inputs and wire up the log sink before running.

        Must be called on the Textual event loop before ``run()``.
        Returns immediately — the worker runs in the background.
        """
        if not self._job.selected_mods:
            self._on_error("No mods selected")
            return

        self._start_time = time.monotonic()
        self._attach_log_sink()

    def stop(self) -> None:
        """Cancel the pipeline and detach the log sink."""
        self._job.cancel()
        self._detach_log_sink()

    async def run(self) -> None:
        """Execute the translation pipeline (async worker entry point).

        Call this from ``Screen.run_worker(runner.run, ...)``.
        """
        self._job.settings.debug = self._is_debug
        try:
            await self._job.run()
        except asyncio.CancelledError:
            self._on_error("Cancelled")
            raise

        if self._job.status == JobStatus.DONE:
            assert self._job.result is not None
            self._on_done(self._job.result)
        else:
            self._on_error(self._job.error or "Pipeline failed — see logs")

    # -- internal ------------------------------------------------------

    def _bridge_progress(self, event: str, **kw: Any) -> None:
        """Forward progress reporter events to ``on_progress`` (thread-safe)."""
        with contextlib.suppress(Exception):
            self._on_progress(event, dict(kw))

    def _attach_log_sink(self) -> None:
        """Route INFO+ log messages to ``on_log`` (non-blocking, thread-safe)."""

        def _sink(msg: str) -> None:
            stripped = msg.strip()
            if stripped.startswith("Inline QA"):
                return
            line = f"[dim]{stripped}[/]"
            self._on_log(line)

        self._log_sink_id = add_callback_sink(_sink, level="INFO")

    def _detach_log_sink(self) -> None:
        if self._log_sink_id is not None:
            with contextlib.suppress(ValueError):
                logger.remove(self._log_sink_id)
            self._log_sink_id = None
