"""Mirror ProgressReporter events to the terminal in dev mode.

The web UI streams progress to the browser via SSE; this module duplicates
key TUI log lines to loguru so ``mova --dev`` shows live output in the terminal.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from loguru import logger

from app.utils.progress import ProgressReporter


def _on_progress(event: str, **data: Any) -> None:
    if event == "title":
        logger.info(str(data.get("text", "")))
    elif event == "translated_entry":
        src = str(data.get("source", "")).replace("\n", "\\n")
        trn = str(data.get("translated", "")).replace("\n", "\\n")
        logger.info('  "{}" → "{}"', src, trn)
    elif event == "mod_file_complete":
        file_path = str(data.get("file_path", ""))
        name = Path(file_path).name or file_path
        duration_ms = int(data.get("duration_ms", 0))
        errors = int(data.get("errors", 0))
        err_part = f", {errors} failed" if errors else ""
        logger.info("  {}: done in {:.1f}s{}", name, duration_ms / 1000, err_part)
    elif event == "mod_complete":
        mod_name = str(data.get("mod_name", ""))
        translated = int(data.get("translated", 0))
        total = int(data.get("total", 0))
        failed = int(data.get("failed", 0))
        if total > 0:
            fail_part = f", {failed} failed" if failed else ""
            logger.info("✓ {} ({}/{}{})", mod_name, translated, total, fail_part)
        else:
            logger.info("✓ {} done", mod_name)


def attach_dev_progress_logger(reporter: ProgressReporter) -> None:
    """Subscribe *reporter* to emit progress lines to the terminal."""
    reporter.subscribe(_on_progress)
