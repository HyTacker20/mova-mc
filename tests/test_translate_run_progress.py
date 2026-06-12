"""Tests for TUI progress formatting and translate-run helpers."""

from __future__ import annotations

import pytest

from app.interfaces.tui.formatting import (
    estimate_eta_seconds,
    format_duration,
    format_duration_seconds,
    format_progress_pct,
)


class TestFormatting:
    def test_format_duration_ms(self) -> None:
        assert format_duration(500) == "500 ms"
        assert format_duration(2500) == "2.5 s"
        assert format_duration(90_000) == "1m 30s"

    def test_format_duration_seconds(self) -> None:
        assert format_duration_seconds(2.5) == "2.5 s"

    def test_format_progress_pct(self) -> None:
        assert format_progress_pct(2.4, 5) == 48
        assert format_progress_pct(0, 0) == 0
        assert format_progress_pct(10, 10) == 100

    def test_estimate_eta_seconds(self) -> None:
        assert estimate_eta_seconds(0, 100, 10.0) is None
        assert estimate_eta_seconds(50, 100, 0.5) is None
        eta = estimate_eta_seconds(50, 100, 10.0)
        assert eta is not None
        assert abs(eta - 10.0) < 0.01


@pytest.mark.asyncio
async def test_translate_run_step_has_stats_widgets() -> None:
    """TranslateRunStep mounts stats and file labels."""
    from textual.app import App
    from textual.widgets import ProgressBar

    from app.interfaces.tui.steps.translate_run import TranslateRunStep

    class _TestApp(App):
        pass

    app = _TestApp()
    async with app.run_test(size=(100, 30)):
        step = TranslateRunStep()
        await app.mount(step)
        assert step.query_one("#translate-stats")
        assert step.query_one("#translate-file")
        assert step.query_one("#qa-progress")


@pytest.mark.asyncio
async def test_translate_run_step_update_qa() -> None:
    """update_qa drives the QA progress bar and label."""
    from textual.app import App
    from textual.widgets import Label, ProgressBar

    from app.interfaces.tui.steps.translate_run import TranslateRunStep

    class _TestApp(App):
        pass

    app = _TestApp()
    async with app.run_test(size=(100, 30)):
        step = TranslateRunStep()
        await app.mount(step)
        step.update_qa(3, 10)
        bar = step.query_one("#qa-progress", ProgressBar)
        assert bar.progress == 3
        assert bar.total == 10
        label_text = str(step.query_one("#qa-progress-label", Label).content)
        assert "3/10" in label_text
        assert "30" in label_text
