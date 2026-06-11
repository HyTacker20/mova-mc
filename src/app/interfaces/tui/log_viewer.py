"""Log viewer — full-screen scrollable view of the translation log."""

from __future__ import annotations

import contextlib
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import ClassVar

from textual import events
from textual.app import ComposeResult
from textual.binding import Binding, BindingType
from textual.screen import ModalScreen
from textual.widgets import Footer, Label, RichLog

from ...logging_config import get_log_file_path
from .i18n import get_locale_from_app, t
from .key_bindings import layout_binding


class LogViewer(ModalScreen):
    """Full-screen log viewer — loads translation.log for review."""

    DEFAULT_CSS = """
    LogViewer {
        background: $background 95%;
        align: center middle;
    }
    LogViewer > #log-container {
        width: 90%;
        height: 90%;
        border: solid $accent;
        background: $surface;
    }
    LogViewer > #log-container > #log-header {
        text-style: bold;
        color: $accent;
        padding: 0 1;
        height: 1;
    }
    LogViewer > #log-container > RichLog {
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

    def __init__(self) -> None:
        super().__init__()
        self._log_text: str = ""
        self._displayed_text: str = ""

    def compose(self) -> ComposeResult:
        from textual.containers import Container

        locale = get_locale_from_app(self.app)
        with Container(id="log-container"):
            yield Label(t("logviewer.title", locale), id="log-header")
            yield RichLog(
                id="log-viewer-content",
                highlight=True,
                markup=True,
                wrap=True,
                max_lines=10_000,
            )
        yield Footer()

    def on_mount(self) -> None:
        locale = get_locale_from_app(self.app)
        log_path = Path(get_log_file_path())
        log_widget = self.query_one("#log-viewer-content", RichLog)
        log_widget.can_focus = True

        if not log_path.exists():
            log_widget.write(t("logviewer.not_found", locale))
            return

        try:
            text = log_path.read_text(encoding="utf-8")
            if not text.strip():
                log_widget.write(t("logviewer.empty", locale))
                return

            lines = text.splitlines()
            tail = lines[-500:] if len(lines) > 500 else lines
            for line in tail:
                log_widget.write(line)
            log_widget.write(
                f"\n[dim]{t('logviewer.footer', locale, shown=len(tail), total=len(lines), name=log_path.name)}[/]"
            )

            self._log_text = text
            self._displayed_text = "\n".join(tail)
        except Exception as e:
            log_widget.write(t("logviewer.read_error", locale, error=str(e)))

    def action_close(self) -> None:
        self.app.pop_screen()

    def _copy_to_clipboard(self, text: str) -> None:
        if not text.strip():
            self.app.notify("⚠ Nothing to copy", timeout=2)
            return
        ok = False
        tmp = ""
        if sys.platform == "win32":
            try:
                with tempfile.NamedTemporaryFile(
                    mode="w", encoding="utf-8", suffix=".txt", delete=False
                ) as f:
                    f.write(text)
                    tmp = f.name
                subprocess.run(
                    [
                        "powershell",
                        "-NoProfile",
                        "-Command",
                        f"Get-Content -Encoding UTF8 '{tmp}' | Set-Clipboard",
                    ],
                    check=True,
                    timeout=10,
                )
                ok = True
            except (subprocess.SubprocessError, OSError):
                pass
            finally:
                if tmp:
                    with contextlib.suppress(Exception):
                        Path(tmp).unlink(missing_ok=True)
        if not ok:
            try:
                import pyperclip  # type: ignore[import-untyped]
                pyperclip.copy(text)
                ok = True
            except (ImportError, Exception):
                pass
        if not ok:
            try:
                import base64
                encoded = base64.b64encode(text.encode("utf-8")).decode("ascii")
                print(f"\x1b]52;c;{encoded}\a", end="", flush=True)
                ok = True
            except Exception:
                pass
        locale = get_locale_from_app(self.app)
        if ok:
            lines = text.count("\n") + 1
            self.app.notify(t("notify.copied", locale, lines=lines), timeout=2)
        else:
            self.app.notify(t("notify.copy_failed", locale), timeout=3)

    def _get_log_text(self) -> str:
        return self._log_text

    def on_mouse_down(self, event: events.MouseDown) -> None:
        if event.button != 3:
            return
        event.stop()

        try:
            widget, _region = self.get_widget_at(event.x, event.y)
        except Exception:
            self._copy_to_clipboard(self._log_text)
            return

        text = ""
        if isinstance(widget, RichLog):
            text = self._displayed_text
        elif isinstance(widget, Label):
            text = str(widget.content)
        else:
            text = ""

        if text.strip():
            self._copy_to_clipboard(text)
        else:
            self._copy_to_clipboard(self._displayed_text)

    def on_mouse_up(self, event: events.MouseUp) -> None:
        if event.button == 3:
            event.stop()
