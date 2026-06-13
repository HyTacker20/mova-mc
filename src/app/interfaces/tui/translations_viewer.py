"""Translations viewer — full-screen scrollable view of all source→target pairs."""

from __future__ import annotations

from typing import ClassVar

from textual.app import ComposeResult
from textual.binding import Binding, BindingType
from textual.containers import Container
from textual.screen import ModalScreen
from textual.widgets import Footer, Label, RichLog

from ...application.pipeline import PipelineResult
from ...domain.models import TranslationResult
from ...domain.qa_display import format_qa_rich_lines
from .i18n import get_locale_from_app, t
from .key_bindings import layout_binding


class TranslationsViewer(ModalScreen):
    """Full-screen viewer showing every translated entry, grouped by mod."""

    DEFAULT_CSS = """
    TranslationsViewer {
        background: $background 95%;
        align: center middle;
    }
    TranslationsViewer > #viewer-container {
        width: 90%;
        height: 90%;
        border: solid $accent;
        background: $surface;
    }
    TranslationsViewer > #viewer-container > #viewer-header {
        text-style: bold;
        color: $accent;
        padding: 0 1;
        height: 1;
    }
    TranslationsViewer > #viewer-container > #viewer-subtitle {
        color: $text-muted;
        padding: 0 1;
        height: 1;
    }
    TranslationsViewer > #viewer-container > RichLog {
        width: 100%;
        height: 1fr;
        overflow-y: auto;
        scrollbar-gutter: stable;
    }
    """

    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("escape", "close", "Close", show=True),
        *layout_binding("q", "close", "Close", show=False),
        *layout_binding("ctrl+c", "close", "Close", show=False),
    ]

    def compose(self) -> ComposeResult:
        locale = get_locale_from_app(self.app)
        with Container(id="viewer-container"):
            yield Label(t("translations.title", locale), id="viewer-header")
            yield Label(t("translations.subtitle", locale), id="viewer-subtitle")
            yield RichLog(
                id="translations-log",
                highlight=True,
                markup=True,
                wrap=True,
                max_lines=100_000,
            )
        yield Footer()

    def action_close(self) -> None:
        self.app.pop_screen()

    def on_mount(self) -> None:
        locale = get_locale_from_app(self.app)
        log = self.query_one("#translations-log", RichLog)
        log.can_focus = True
        wiz = self.app.wizard_state  # type: ignore[attr-defined]
        result: PipelineResult | None = wiz.pipeline_result

        if result is None:
            log.write(t("translations.no_result", locale))
            return

        total_entries = 0
        for mod in result.mods:
            if not mod.selected:
                continue

            mod_entries = 0
            mod_lines: list[str] = []
            for lang_file in mod.lang_files:
                for unit in lang_file.units:
                    if not isinstance(unit, TranslationResult):
                        continue
                    key = unit.unit.key
                    src = unit.unit.source_text.replace("\n", "\\n")
                    tgt = unit.translated_text.replace("\n", "\\n")

                    mod_lines.append(f"  [bold]{key}[/]")
                    if unit.success:
                        mod_lines.append(f"    [white]{src}[/]  [green]→[/]  [bold white]{tgt}[/]")
                    else:
                        mod_lines.append(f"    [white]{src}[/]  [green]→[/]  [red]{tgt}[/]")
                    mod_lines.extend(format_qa_rich_lines(unit))
                    mod_entries += 1

            if mod_entries > 0:
                log.write(f"\n[bold yellow]{t('translations.mod_header', locale, name=mod.name, count=mod_entries)}[/]")
                for line in mod_lines:
                    log.write(line)
                total_entries += mod_entries

        if total_entries == 0:
            log.write(t("translations.none", locale))
        else:
            log.write(f"\n[bold]{t('translations.total', locale, count=total_entries)}[/]")
