"""Step 2: Paths configuration — languages, mods folder, output path."""

from __future__ import annotations

from pathlib import Path

from textual.app import ComposeResult
from textual.containers import Container, Horizontal
from textual.widget import Widget
from textual.widgets import Button, Input, Label, Select

from ....domain.languages import LANGUAGE_NAMES
from ..i18n import get_locale_from_app, t
from . import StepBack, StepComplete

_LANGUAGE_OPTIONS_CACHE: list[tuple[str, str]] | None = None


def _language_options() -> list[tuple[str, str]]:
    global _LANGUAGE_OPTIONS_CACHE
    if _LANGUAGE_OPTIONS_CACHE is None:
        _LANGUAGE_OPTIONS_CACHE = sorted(
            ((f"{name}", code) for code, name in LANGUAGE_NAMES.items()),
            key=lambda x: x[0].lower(),
        )
    return _LANGUAGE_OPTIONS_CACHE


class PathsStep(Widget):
    """Configure source/target languages and file paths."""

    initial_source: str = "en_US"
    initial_target: str = "es_ES"
    initial_mods_path: str = "./mods"
    initial_output_path: str = "./translated_mods"

    DEFAULT_CSS = """
    PathsStep > .field-label { text-style: bold; color: $text; margin: 0; }
    PathsStep > Select { margin: 0 0 1 0; max-width: 60; }
    PathsStep > Input { margin: 0 0 1 0; max-width: 60; }
    PathsStep > #lang-hint { color: $text-muted; text-style: italic; margin: 0 0 1 0; }
    PathsStep > #target-hint { color: $text-muted; text-style: italic; margin: 0 0 1 0; }
    PathsStep > #lang-warning { color: $warning; text-style: bold; margin: 0 0 1 0; }
    PathsStep > #paths-error { color: $error; text-style: bold; margin: 0 0 1 0; }
    PathsStep > #output-section.hidden { display: none; height: 0; }
    """

    def compose(self) -> ComposeResult:
        locale = get_locale_from_app(self.app)
        opts = _language_options()

        yield Label(t("paths.title", locale), classes="step-title")

        yield Label(t("paths.source", locale), classes="field-label")
        yield Label(t("paths.source_hint", locale), id="lang-hint")
        yield Select(
            opts,
            prompt=t("paths.source_prompt", locale),
            value=self.initial_source,
            id="source-lang",
        )

        yield Label(t("paths.target", locale), classes="field-label")
        yield Label(t("paths.target_hint", locale), id="target-hint")
        yield Label("", id="lang-warning")
        yield Select(
            opts,
            prompt=t("paths.target_prompt", locale),
            value=self.initial_target,
            id="target-lang",
        )

        yield Label(t("paths.mods_folder", locale), classes="field-label")
        yield Input(
            value=self.initial_mods_path,
            placeholder=t("paths.mods_placeholder", locale),
            id="mods-path",
        )
        yield Label("", id="paths-error")

        with Container(id="output-section"):
            yield Label(t("paths.output_folder", locale), classes="field-label", id="output-label")
            yield Input(
                value=self.initial_output_path,
                placeholder=t("paths.output_placeholder", locale),
                id="output-path",
            )

        yield Horizontal(
            Button(t("nav.back", locale), id="back-btn"),
            Button(t("paths.scan_mods", locale), id="next-btn", variant="primary"),
            id="nav-row",
        )

    def on_mount(self) -> None:
        self.refresh_on_show()

    def apply_locale(self) -> None:
        if not self.is_mounted:
            return
        locale = get_locale_from_app(self.app)
        self.query_one(".step-title", Label).update(t("paths.title", locale))
        labels = list(self.query(".field-label"))
        if len(labels) >= 1:
            labels[0].update(t("paths.source", locale))  # type: ignore[attr-defined]
        self.query_one("#lang-hint", Label).update(t("paths.source_hint", locale))
        if len(labels) >= 2:
            labels[1].update(t("paths.target", locale))  # type: ignore[attr-defined]
        self.query_one("#target-hint", Label).update(t("paths.target_hint", locale))
        if len(labels) >= 3:
            labels[2].update(t("paths.mods_folder", locale))  # type: ignore[attr-defined]
        self.query_one("#output-label", Label).update(t("paths.output_folder", locale))
        self.query_one("#mods-path", Input).placeholder = t("paths.mods_placeholder", locale)
        self.query_one("#output-path", Input).placeholder = t("paths.output_placeholder", locale)
        self.query_one("#back-btn", Button).label = t("nav.back", locale)
        self.query_one("#next-btn", Button).label = t("paths.scan_mods", locale)

    def refresh_on_show(self) -> None:
        """Show/hide output path based on output_mode from settings."""
        try:
            wiz = self.app.wizard_state  # type: ignore[attr-defined]
            section = self.query_one("#output-section", Container)
            if wiz.settings.output_mode == "separate":
                section.remove_class("hidden")
            else:
                section.add_class("hidden")
        except Exception:
            pass

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "next-btn":
            locale = get_locale_from_app(self.app)
            src = self.query_one("#source-lang", Select)
            tgt = self.query_one("#target-lang", Select)
            warning = self.query_one("#lang-warning", Label)
            paths_error = self.query_one("#paths-error", Label)

            if not src.value or not tgt.value:
                warning.update(t("paths.lang_required", locale))
                return
            if src.value == tgt.value:
                warning.update(t("paths.lang_same", locale))
                return
            warning.update("")

            mods_path = self.query_one("#mods-path", Input).value.strip()
            if not mods_path:
                paths_error.update(t("paths.error_empty", locale))
                return
            path = Path(mods_path)
            if not path.exists() or not path.is_dir():
                paths_error.update(t("paths.error_not_dir", locale))
                return
            paths_error.update("")

            self.post_message(
                StepComplete(
                    {
                        "source_lang": str(src.value),
                        "target_lang": str(tgt.value),
                        "mods_path": mods_path,
                        "output_path": self.query_one("#output-path", Input).value,
                    }
                )
            )
        elif event.button.id == "back-btn":
            self.post_message(StepBack())
