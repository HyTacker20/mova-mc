"""Summary step — display translation results after pipeline completes."""

from __future__ import annotations

from typing import ClassVar

from loguru import logger
from textual.app import ComposeResult
from textual.binding import Binding, BindingType
from textual.containers import Horizontal
from textual.events import Key
from textual.widget import Widget
from textual.widgets import Button, DataTable, Label

from ....domain.stats import OverallStats
from ..formatting import format_duration
from ..i18n import get_locale_from_app, t
from . import StepCancel, StepComplete


class SummaryStep(Widget):
    """Display translation results after pipeline completes."""

    can_focus = True

    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("escape", "go_back", "Back", show=True),
    ]

    DEFAULT_CSS = """\
    SummaryStep > #summary-title { text-style: bold; color: $success; text-align: center; margin: 0 0 1 0; }
    SummaryStep > DataTable { height: auto; margin: 0 0 1 0; }
    SummaryStep > #view-log-hint { color: $text-muted; text-style: italic; text-align: center; margin: 0 0 1 0; }
    SummaryStep > Horizontal { align: center middle; margin: 1 0 0 0; }
    SummaryStep > #button-row-2 { margin: 0 0 1 0; }
    SummaryStep > Horizontal > Button { width: auto; padding: 0 2; margin: 0 1 0 0; }
    SummaryStep .failed-row { color: $error; text-style: bold; }
    """

    _stats: OverallStats | None = None

    def compose(self) -> ComposeResult:
        locale = get_locale_from_app(self.app)
        yield Label(t("summary.title", locale), id="summary-title")
        yield DataTable(id="summary-table")
        yield Horizontal(
            Button(t("summary.back_mods", locale), id="back-btn"),
            Button(t("summary.view_log", locale), id="view-log-btn"),
            Button(t("summary.view_translations", locale), id="view-translations-btn"),
            id="button-row-1",
        )
        yield Label(t("summary.view_log_hint", locale), id="view-log-hint")
        yield Horizontal(
            Button(t("summary.new", locale), id="restart-btn", variant="primary"),
            Button(t("summary.quit", locale), id="quit-btn"),
            id="button-row-2",
        )

    def apply_locale(self) -> None:
        if not self.is_mounted:
            return
        locale = get_locale_from_app(self.app)
        self.query_one("#summary-title", Label).update(t("summary.title", locale))
        self.query_one("#view-log-hint", Label).update(t("summary.view_log_hint", locale))
        self.query_one("#back-btn", Button).label = t("summary.back_mods", locale)
        self.query_one("#view-log-btn", Button).label = t("summary.view_log", locale)
        self.query_one("#view-translations-btn", Button).label = t("summary.view_translations", locale)
        self.query_one("#restart-btn", Button).label = t("summary.new", locale)
        self.query_one("#quit-btn", Button).label = t("summary.quit", locale)
        self._render_stats()

    def set_stats(self, stats: OverallStats) -> None:
        self._stats = stats
        if self.is_mounted:
            self._render_stats()

    def on_mount(self) -> None:
        self._render_stats()

    def _render_stats(self) -> None:
        stats = self._stats
        if stats is None:
            return
        locale = get_locale_from_app(self.app)
        table = self.query_one("#summary-table", DataTable)
        table.clear()
        table.add_columns(t("summary.metric", locale), t("summary.value", locale))
        table.add_row(t("summary.mods", locale), str(stats.translated_mods))
        table.add_row(t("summary.entries", locale), str(stats.translated_entries))
        failed_label = t("summary.failed", locale)
        failed_value = str(stats.failed_entries)
        if stats.failed_entries > 0:
            failed_value = f"[red bold]{failed_value}[/]"
        table.add_row(failed_label, failed_value)
        table.add_row(t("summary.duration", locale), format_duration(stats.total_duration_ms))
        table.add_row(t("summary.provider", locale), stats.provider)
        table.add_row(
            t("summary.langs", locale),
            f"{stats.source_lang} → {stats.target_lang}",
        )

    def action_go_back(self) -> None:
        logger.debug("SummaryStep.action_go_back() CALLED")
        from ..wizard import WizardScreen

        parent = self.parent
        while parent is not None:
            if isinstance(parent, WizardScreen):
                parent.go_back()
                return
            parent = parent.parent if hasattr(parent, "parent") else None

    def on_key(self, event: Key) -> None:
        if event.key == "escape":
            self.action_go_back()
            event.stop()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "back-btn":
            self.action_go_back()
        elif event.button.id == "restart-btn":
            self.post_message(StepComplete({"restart": True}))
        elif event.button.id == "quit-btn":
            self.post_message(StepCancel())
        elif event.button.id == "view-log-btn":
            from ..log_viewer import LogViewer

            self.app.push_screen(LogViewer())
        elif event.button.id == "view-translations-btn":
            from ..translations_viewer import TranslationsViewer

            self.app.push_screen(TranslationsViewer())
