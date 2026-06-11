"""Pipeline runner — extracted from WizardScreen to separate orchestration from UI.

Runs the translation pipeline on an asyncio worker, bridges progress events
from worker threads to the Textual message bus, and manages the loguru→TUI sink.

The runner accepts callbacks instead of reaching into ``TranslateRunStep`` widgets
directly, so it can be tested independently of the TUI.
"""

from __future__ import annotations

import asyncio
import contextlib
import shutil
import time
from collections.abc import Callable
from typing import Any

from loguru import logger

from ...application.pipeline import (
    build_context,
    run_pipeline_async,
)
from ...core.mod_scanner import ModInfo, modinfo_to_domain_mod
from ...core.settings import Settings
from ...domain.stats import OverallStats
from ...logging_config import add_callback_sink
from ...utils.cancellation import cancel_token
from ...utils.progress import ProgressReporter


class PipelineRunner:
    """Encapsulates pipeline execution lifecycle for the TUI wizard.

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
        self._settings = settings
        self._selected = selected_mods
        self._on_progress = on_progress
        self._on_log = on_log
        self._on_done = on_done
        self._on_error = on_error
        self._is_debug = is_debug

        self._reporter = ProgressReporter()
        self._log_sink_id: int | None = None
        self._start_time: float = 0.0

    # -- public API ----------------------------------------------------

    @property
    def reporter(self) -> ProgressReporter:
        """The progress reporter feeding events to ``on_progress``."""
        return self._reporter

    def start(self) -> None:
        """Validate inputs, wire up progress, and launch the pipeline worker.

        Must be called on the Textual event loop (uses ``Screen.run_worker``).
        Returns immediately — the worker runs in the background.
        The caller is responsible for calling ``run_worker`` with the returned
        coroutine function.
        """
        cancel_token.clear()

        if not self._selected:
            self._on_error("No mods selected")
            return

        self._start_time = time.monotonic()
        self._reporter.subscribe(self._bridge_progress)
        self._attach_log_sink()

    def stop(self) -> None:
        """Cancel the pipeline and detach the log sink."""
        cancel_token.set()
        self._detach_log_sink()

    async def run(self) -> None:
        """Execute the translation pipeline (async worker entry point).

        Call this from ``Screen.run_worker(runner.run, ...)``.
        """
        settings = self._settings
        settings.debug = self._is_debug

        ctx = None
        try:
            mods = [modinfo_to_domain_mod(m) for m in self._selected]
            ctx = build_context(settings, self._reporter, model=settings.model)
            result = await run_pipeline_async(ctx, mods)
            self._on_done(result.stats)
        except asyncio.CancelledError:
            logger.info("Pipeline cancelled by system shutdown")
            self._on_error("Cancelled")
            raise
        except KeyboardInterrupt:
            logger.info("Pipeline cancelled by user")
            self._on_error("Cancelled")
        except Exception:
            logger.exception("Pipeline failed")
            self._on_error("Pipeline failed — see logs")
        finally:
            if ctx is not None and ctx.workspace.exists():
                shutil.rmtree(str(ctx.workspace), ignore_errors=True)

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
