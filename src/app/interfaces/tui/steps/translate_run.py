"""Step 5: Live translation progress — bars and log output."""

from __future__ import annotations

from pathlib import Path

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widget import Widget
from textual.widgets import Button, Label, ProgressBar, RichLog

from ..formatting import format_duration_seconds, format_progress_pct
from ..i18n import get_locale_from_app, t
from . import StepBack


class TranslateRunStep(Widget):
    """Live translation progress with bars and log output."""

    DEFAULT_CSS = """
    TranslateRunStep {
        layout: vertical;
        width: 100%;
        height: 100%;
    }
    TranslateRunStep > #translate-phase {
        text-style: bold; color: $accent; text-align: center; width: 100%; margin: 0 0 1 0;
    }
    TranslateRunStep > #translate-header {
        width: 100%; height: auto; margin: 0 0 1 0;
    }
    TranslateRunStep > #translate-header > Label {
        width: 100%; text-align: center; color: $text-muted; height: 1; margin: 0;
    }
    TranslateRunStep > #translate-header > #translate-stats {
        margin: 1 0 0 0;
    }
    TranslateRunStep > #translate-error {
        color: $error; text-style: bold; text-align: center; width: 100%; margin: 0 0 1 0;
        display: none;
    }
    TranslateRunStep > #translate-error.visible { display: block; }
    TranslateRunStep > #error-nav { align: center middle; width: 100%; margin: 0 0 1 0; display: none; }
    TranslateRunStep > #error-nav.visible { display: block; }
    TranslateRunStep > #progress-section {
        width: 100%; height: auto; margin: 0 0 1 0;
    }
    TranslateRunStep .progress-block {
        width: 100%; height: auto; margin: 0 0 1 0;
    }
    TranslateRunStep .progress-block > Label {
        width: 100%; margin: 0 0 0 0; color: $text;
    }
    TranslateRunStep .progress-block > ProgressBar {
        width: 100%; margin: 0; height: 1;
    }
    TranslateRunStep > #log-area {
        width: 100%; height: 1fr; layout: horizontal;
    }
    TranslateRunStep > #log-area > #trans-panel,
    TranslateRunStep > #log-area > #qa-panel {
        width: 1fr; height: 100%; layout: vertical;
    }
    TranslateRunStep > #log-area > #trans-panel {
        margin: 0 1 0 0;
    }
    TranslateRunStep > #log-area > #qa-panel {
        display: none;
    }
    TranslateRunStep > #log-area > #trans-panel > #trans-label,
    TranslateRunStep > #log-area > #qa-panel > #qa-label {
        width: 100%; height: 1; padding: 0 1; margin: 0 0 1 0;
        text-style: bold; background: $panel;
    }
    TranslateRunStep > #log-area > #trans-panel > #trans-label {
        color: $text;
    }
    TranslateRunStep > #log-area > #qa-panel > #qa-label {
        color: $warning;
    }
    TranslateRunStep > #log-area > #trans-panel > RichLog,
    TranslateRunStep > #log-area > #qa-panel > RichLog {
        width: 100%; height: 1fr; background: $background;
    }
    TranslateRunStep > #log-area > #trans-panel > RichLog {
        border: solid $border;
    }
    TranslateRunStep > #log-area > #qa-panel > RichLog {
        border: solid $warning;
    }
    """

    def __init__(self) -> None:
        super().__init__()
        self._log_lines: list[str] = []
        self._qa_log_lines: list[str] = []

    def compose(self) -> ComposeResult:
        locale = get_locale_from_app(self.app)
        yield Label(t("translate.preparing", locale), id="translate-phase")
        with Vertical(id="translate-header"):
            yield Label("", id="translate-mod-name")
            yield Label("", id="translate-file")
            yield Label("", id="translate-stats")
        yield Label("", id="translate-error")
        yield Horizontal(
            Button(t("translate.back_mods", locale), id="back-to-mods-btn"),
            id="error-nav",
        )
        with Vertical(id="progress-section"):
            with Vertical(classes="progress-block"):
                yield Label(t("translate.mods_progress", locale), id="mods-progress-label")
                yield ProgressBar(
                    id="mods-progress",
                    total=100,
                    show_percentage=False,
                    show_eta=False,
                )
            with Vertical(classes="progress-block"):
                yield Label(t("translate.entries_progress", locale), id="entries-progress-label")
                yield ProgressBar(
                    id="entries-progress",
                    total=100,
                    show_percentage=False,
                    show_eta=False,
                )
        with Horizontal(id="log-area"):
            with Vertical(id="trans-panel"):
                yield Label(t("translate.log_label", locale), id="trans-label")
                yield RichLog(
                    id="translate-log",
                    highlight=True,
                    markup=True,
                    max_lines=300,
                    wrap=True,
                )
            with Vertical(id="qa-panel"):
                yield Label(t("translate.qa_label", locale), id="qa-label")
                yield RichLog(
                    id="qa-log",
                    highlight=True,
                    markup=True,
                    max_lines=300,
                    wrap=True,
                )

    def apply_locale(self) -> None:
        if not self.is_mounted:
            return
        locale = get_locale_from_app(self.app)
        self.query_one("#trans-label", Label).update(t("translate.log_label", locale))
        self.query_one("#qa-label", Label).update(t("translate.qa_label", locale))
        self.query_one("#back-to-mods-btn", Button).label = t("translate.back_mods", locale)

    def on_mount(self) -> None:
        self.query_one("#translate-log", RichLog).can_focus = True

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "back-to-mods-btn":
            self.post_message(StepBack())

    def set_phase(self, text: str) -> None:
        self.query_one("#translate-phase", Label).update(text)

    def set_mod_name(self, name: str) -> None:
        locale = get_locale_from_app(self.app)
        self.query_one("#translate-mod-name", Label).update(t("translate.mod", locale, name=name))

    def set_current_file(self, file_path: str) -> None:
        locale = get_locale_from_app(self.app)
        name = Path(file_path).name
        self.query_one("#translate-file", Label).update(
            t("translate.current_file", locale, name=name)
        )

    def update_mods(self, completed: int, total: int, *, fractional: float | None = None) -> None:
        bar = self.query_one("#mods-progress", ProgressBar)
        bar.total = max(total, 1)
        progress = fractional if fractional is not None else float(completed)
        bar.progress = min(progress, float(total))
        locale = get_locale_from_app(self.app)
        display = fractional if fractional is not None else float(completed)
        pct = format_progress_pct(display, total)
        label = t(
            "translate.mods_progress_fmt",
            locale,
            current=f"{display:.1f}" if fractional is not None else str(completed),
            total=str(total),
            pct=str(pct),
        )
        self.query_one("#mods-progress-label", Label).update(label)

    def update_entries(self, done: int, total: int) -> None:
        bar = self.query_one("#entries-progress", ProgressBar)
        bar.total = max(total, 1)
        bar.progress = min(done, total)
        locale = get_locale_from_app(self.app)
        pct = format_progress_pct(done, total)
        label = t(
            "translate.entries_progress_fmt",
            locale,
            current=str(done),
            total=str(total),
            pct=str(pct),
        )
        self.query_one("#entries-progress-label", Label).update(label)

    def update_live_stats(self, elapsed_s: float, eta_s: float | None, failed: int) -> None:
        locale = get_locale_from_app(self.app)
        elapsed_text = format_duration_seconds(elapsed_s)
        if eta_s is not None:
            eta_text = format_duration_seconds(eta_s)
            eta_part = t("translate.stats_eta", locale, time=eta_text)
        else:
            eta_part = t("translate.stats_eta_unknown", locale)
        elapsed_part = t("translate.stats_elapsed", locale, time=elapsed_text)
        failed_part = t("translate.stats_failed", locale, count=str(failed))
        self.query_one("#translate-stats", Label).update(
            f"{elapsed_part}  ·  {eta_part}  ·  {failed_part}"
        )

    def add_log(self, line: str) -> None:
        self._log_lines.append(line)
        log = self.query_one("#translate-log", RichLog)
        log.write(line)
        log.scroll_end(animate=False)

    def add_qa_log(self, line: str) -> None:
        self._qa_log_lines.append(line)
        log = self.query_one("#qa-log", RichLog)
        log.write(line)
        log.scroll_end(animate=False)

    def show_error(self, message: str) -> None:
        locale = get_locale_from_app(self.app)
        err = self.query_one("#translate-error", Label)
        err.update(t("translate.error", locale, error=message))
        err.add_class("visible")
        self.query_one("#error-nav", Horizontal).add_class("visible")

    def clear_error(self) -> None:
        self.query_one("#translate-error", Label).remove_class("visible")
        self.query_one("#error-nav", Horizontal).remove_class("visible")

    def toggle_log(self) -> None:
        log = self.query_one("#translate-log", RichLog)
        log.display = not log.display

    def toggle_qa_log(self) -> None:
        log = self.query_one("#qa-log", RichLog)
        log.display = not log.display

    def set_qa_label(self, text: str) -> None:
        self.query_one("#qa-label", Label).update(text)

    def get_log_text(self) -> str:
        return "\n".join(self._log_lines)

    def get_qa_log_text(self) -> str:
        return "\n".join(self._qa_log_lines)
