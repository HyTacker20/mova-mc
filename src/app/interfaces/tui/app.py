"""Textual application for MovaMC — wizard-based TUI."""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

from textual.app import App, ComposeResult
from textual.binding import Binding, BindingType
from textual.theme import Theme
from textual.widgets import Footer

from ...utils.shutdown import finalize_shutdown, request_shutdown
from .key_bindings import layout_binding
from .theme import DASHBOARD_THEME

if TYPE_CHECKING:
    from .wizard import WizardState


class TranslationApp(App):
    """Step-by-step wizard Textual application for MovaMC."""

    CSS_PATH = "app.tcss"

    THEMES: ClassVar[dict[str, Theme]] = {DASHBOARD_THEME.name: DASHBOARD_THEME}
    theme = "dashboard"

    BINDINGS: ClassVar[list[BindingType]] = [
        *layout_binding("q", "quit", "Quit", show=False),
        *layout_binding("ctrl+c", "quit", "Quit", show=False),
        *layout_binding("ctrl+q", "quit", "Quit", show=False),
        Binding("f1", "show_help", "Help", show=True),
    ]

    wizard_state: WizardState

    def __init__(self, debug: bool = False) -> None:
        self._debug = debug
        from .wizard import WizardState

        self.wizard_state = WizardState()
        super().__init__()

    def compose(self) -> ComposeResult:
        yield Footer()

    def on_ready(self) -> None:
        """Push wizard directly."""
        from .wizard import WizardScreen

        self.install_screen(WizardScreen(), name="wizard")
        self.push_screen("wizard")

    async def action_show_help(self) -> None:
        """Show a quick help notification with keyboard shortcuts."""
        from .i18n import get_locale_from_app, t

        locale = get_locale_from_app(self)
        self.notify(
            t("help.body", locale),
            title=t("help.title", locale),
            severity="information",
            timeout=10,
        )

    def on_unmount(self) -> None:
        """Ensure workers and pipeline cancellation on app teardown."""
        finalize_shutdown()

    async def action_quit(self) -> None:
        """Quit the application."""
        request_shutdown(0)

    def key_escape(self) -> None:
        """FALLBACK — Escape reached App level unhandled."""
        from loguru import logger

        screen = self.screen
        focused = screen.focused if hasattr(screen, "focused") else None
        focused_info = f"focused={type(focused).__name__}[{focused.id}]" if focused is not None else "focused=None"

        # Introspect both binding chains
        chain_repr: list[str] | str = "ERR"
        modal_repr: list[str] | str = "ERR"
        try:
            chain = screen._binding_chain
            chain_repr = []
            for node, bm in chain:
                keys = sorted(bm.key_to_bindings.keys())
                node_name = type(node).__name__
                nid = getattr(node, "id", None)
                chain_repr.append(f"{node_name}(id={nid}, bindings={keys})")
            chain_repr = " → ".join(chain_repr)

            modal = screen._modal_binding_chain
            modal_repr = []
            for node, bm in modal:
                keys = sorted(bm.key_to_bindings.keys())
                node_name = type(node).__name__
                nid = getattr(node, "id", None)
                modal_repr.append(f"{node_name}(id={nid}, bindings={keys})")
            modal_repr = " → ".join(modal_repr)
        except Exception as exc:
            chain_repr = f"chain_error={exc}"
            modal_repr = f"modal_error={exc}"

        logger.debug(
            "App.key_escape() — Escape UNHANDLED. screen={}, {}, binding_chain=[{}], modal_chain=[{}]",
            type(screen).__name__,
            focused_info,
            chain_repr,
            modal_repr,
        )

    def key_ctrl_c(self) -> None:
        """Fallback handler for Ctrl+C at the App level."""
        request_shutdown(0)
