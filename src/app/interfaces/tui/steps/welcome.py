"""Step 0: Welcome — introduction step with description and start button."""

from __future__ import annotations

import contextlib
from typing import ClassVar

from textual.app import ComposeResult
from textual.binding import Binding, BindingType
from textual.containers import Horizontal
from textual.widget import Widget
from textual.widgets import Button, Label, Select

from ....__version__ import __version__
from ..i18n import get_locale_from_app, t
from . import StepComplete


class WelcomeStep(Widget):
    """Welcome / introduction step with description."""

    can_focus = True

    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("enter", "start_wizard", "Start", show=False),
    ]

    DEFAULT_CSS = """
    WelcomeStep > #welcome-version {
        text-align: center;
        width: 100%;
        color: $text-muted;
        margin: 0 0 1 0;
    }
    WelcomeStep > #config-indicator {
        text-align: center;
        width: 100%;
        color: $success;
        margin: 0 0 0 0;
        text-style: italic;
    }
    WelcomeStep > #welcome-title {
        text-style: bold;
        color: $accent;
        text-align: center;
        width: 100%;
        margin: 0 0 1 0;
    }
    WelcomeStep > #welcome-desc {
        text-align: center;
        width: 100%;
        color: $text-muted;
        margin: 0 0 2 0;
    }
    WelcomeStep > #locale-row { align: center middle; margin: 0 0 1 0; height: 3; }
    WelcomeStep > #locale-row > Label { margin: 0 1 0 0; }
    WelcomeStep > #locale-row > Select { width: 24; }
    WelcomeStep > #start-row { align: center middle; margin: 2 0 0 0; }
    WelcomeStep > #start-row > Button { width: 30; }
    """

    def compose(self) -> ComposeResult:
        locale = get_locale_from_app(self.app)
        yield Label(t("welcome.title", locale), id="welcome-title")
        yield Label(f"v{__version__}", id="welcome-version")
        yield Label("", id="config-indicator")
        yield Label(t("welcome.desc", locale), id="welcome-desc")
        yield Horizontal(
            Label(t("welcome.locale", locale), id="locale-label"),
            Select(
                [("English", "en"), ("Українська", "uk")],
                value=locale,
                id="locale-select",
            ),
            id="locale-row",
        )
        yield Horizontal(
            Button(t("welcome.start", locale), id="start-btn", variant="primary"),
            id="start-row",
        )

    def apply_locale(self) -> None:
        """Refresh all user-visible strings for the current locale."""
        if not self.is_mounted:
            return
        locale = get_locale_from_app(self.app)
        self.query_one("#welcome-title", Label).update(t("welcome.title", locale))
        self.query_one("#welcome-desc", Label).update(t("welcome.desc", locale))
        self.query_one("#locale-label", Label).update(t("welcome.locale", locale))
        self.query_one("#start-btn", Button).label = t("welcome.start", locale)
        self._update_config_indicator()

    def _update_config_indicator(self) -> None:
        locale = get_locale_from_app(self.app)
        try:
            wiz = self.app.wizard_state  # type: ignore[attr-defined]
            indicator = self.query_one("#config-indicator", Label)
            if wiz.config_path:
                indicator.update(t("welcome.config_loaded", locale, name=wiz.config_path.name))
            else:
                indicator.update("")
        except Exception:
            pass

    def on_mount(self) -> None:
        self._update_config_indicator()

    def on_select_changed(self, event: Select.Changed) -> None:
        if event.select.id != "locale-select" or not event.value:
            return
        if not self.is_mounted:
            return
        wiz = self.app.wizard_state  # type: ignore[attr-defined]
        wiz.ui_locale = str(event.value)
        self.apply_locale()
        # Save ONLY the locale preference to the config file — never the
        # full settings dict.  Writing the full dict risks overwriting
        # provider/model/path values with defaults if the config wasn't
        # loaded properly (e.g. find_config_file returned None).
        try:
            from ....core.config_loader import load_config, save_config

            config_path = wiz.config_path
            if config_path is not None and config_path.is_file():
                data = load_config(config_path)
                data["ui_locale"] = wiz.ui_locale
                save_config(data, config_path)
        except Exception:
            pass
        from ..wizard import WizardScreen

        screen = self.app.screen
        if isinstance(screen, WizardScreen):
            screen.on_locale_changed()

    def action_start_wizard(self) -> None:
        with contextlib.suppress(Exception):
            self.query_one("#start-btn", Button).press()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "start-btn":
            self.post_message(StepComplete())
