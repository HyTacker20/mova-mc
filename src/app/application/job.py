"""UI-agnostic translation job abstraction.

TranslationJob encapsulates a single pipeline run — its settings, progress
reporter, lifecycle status, and result.  Both the TUI (PipelineRunner) and the
future web API consume this as their execution unit.

JobRegistry provides in-memory job tracking for Phase 1 (local single-user).
Swap the storage backend for Phase 3 (Redis/DB, multi-user SaaS) without
changing the interface consumed by callers.
"""

from __future__ import annotations

import asyncio
import shutil
import uuid
from dataclasses import dataclass, field
from enum import Enum

from loguru import logger

from ..core.mod_scanner import ModInfo, modinfo_to_domain_mod
from ..core.settings import Settings
from ..domain.stats import OverallStats
from ..utils.cancellation import cancel_token
from ..utils.progress import ProgressReporter
from .pipeline import build_context, run_pipeline_async


class JobStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    DONE = "done"
    CANCELLED = "cancelled"
    FAILED = "failed"


@dataclass
class TranslationJob:
    """Encapsulates a single translation pipeline execution.

    Create with ``TranslationJob(settings, selected_mods)``.
    Subscribe to ``reporter`` before calling ``run()``.
    """

    settings: Settings
    selected_mods: list[ModInfo]
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    reporter: ProgressReporter = field(default_factory=ProgressReporter)
    status: JobStatus = field(default=JobStatus.PENDING)
    result: OverallStats | None = field(default=None)
    error: str | None = field(default=None)

    async def run(self) -> None:
        """Execute the translation pipeline.

        Updates ``status``, ``result``, and ``error`` in-place.
        Re-raises ``asyncio.CancelledError`` so callers can propagate it.
        """
        cancel_token.clear()
        self.status = JobStatus.RUNNING
        ctx = None
        try:
            mods = [modinfo_to_domain_mod(m) for m in self.selected_mods]
            ctx = build_context(self.settings, self.reporter, model=self.settings.model)
            pipeline_result = await run_pipeline_async(ctx, mods)
            self.result = pipeline_result.stats
            self.status = JobStatus.DONE
        except asyncio.CancelledError:
            logger.info("Pipeline cancelled by user")
            self.status = JobStatus.CANCELLED
            self.error = "Cancelled"
        except KeyboardInterrupt:
            # Actual OS-level Ctrl+C (sys.exit path).  Handled identically to
            # the cooperative CancelledError path above.
            logger.info("Pipeline cancelled by system shutdown")
            self.status = JobStatus.CANCELLED
            self.error = "Cancelled"
        except Exception:
            logger.exception("Pipeline failed")
            self.status = JobStatus.FAILED
            self.error = "Pipeline failed — see logs"
        finally:
            # Clean up workspace only on success.  On cancellation / failure
            # a worker thread (launched via asyncio.to_thread) may still be
            # iterating the temp tree — deleting it here races the thread and
            # causes FileNotFoundError inside os.walk / ZipFile.write.
            if self.status == JobStatus.DONE and ctx is not None and ctx.workspace.exists():
                shutil.rmtree(str(ctx.workspace), ignore_errors=True)

    def cancel(self) -> None:
        """Request cancellation via the global cancel token."""
        cancel_token.set()


class JobRegistry:
    """In-memory job store for Phase 1 (local single-user).

    Replace the storage backend for Phase 3 (Redis/DB, multi-user SaaS).
    Interface is intentionally minimal: register → get → all.
    """

    def __init__(self) -> None:
        self._jobs: dict[str, TranslationJob] = {}

    def register(self, job: TranslationJob) -> TranslationJob:
        self._jobs[job.id] = job
        return job

    def get(self, job_id: str) -> TranslationJob | None:
        return self._jobs.get(job_id)

    def all(self) -> list[TranslationJob]:
        return list(self._jobs.values())
