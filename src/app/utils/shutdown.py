"""Cooperative shutdown helpers for clean process exit.

Ensures Ctrl+C / SIGTERM cancel pipeline workers and release the console
launcher (``mova.exe``) so ``uv run`` can reinstall the package.
"""

from __future__ import annotations

import atexit
import contextlib
import signal
import sys
import threading
from typing import TYPE_CHECKING

from .cancellation import cancel_token

if TYPE_CHECKING:
    from textual.app import App

_app_ref: App | None = None
_handlers_installed = False
_lock = threading.Lock()
_interrupt_count = 0


def register_app(app: App) -> None:
    """Register the running Textual app for signal-driven shutdown."""
    global _app_ref
    _app_ref = app


def clear_app() -> None:
    """Clear the registered app after ``App.run()`` returns."""
    global _app_ref, _interrupt_count
    _app_ref = None
    _interrupt_count = 0


def _cancel_workers(app: App) -> None:
    with contextlib.suppress(Exception):
        app.workers.cancel_all()


def finalize_shutdown() -> None:
    """Last-chance cleanup; safe to call multiple times."""
    cancel_token.set()
    app = _app_ref
    if app is not None:
        _cancel_workers(app)


def request_shutdown(exit_code: int = 0) -> None:
    """Cancel work and ask the Textual app to exit."""
    cancel_token.set()
    app = _app_ref
    if app is None:
        return
    _cancel_workers(app)
    with contextlib.suppress(Exception):
        app.exit(return_code=exit_code)


def _handle_signal(signum: int, _frame: object | None) -> None:
    global _interrupt_count
    _interrupt_count += 1
    if _interrupt_count == 1:
        request_shutdown(0)
        return
    # Second interrupt — force immediate exit (unblocks stuck I/O).
    finalize_shutdown()
    raise SystemExit(128 + signum)


def install_signal_handlers() -> None:
    """Install SIGINT/SIGTERM handlers once per process."""
    global _handlers_installed
    with _lock:
        if _handlers_installed:
            return
        _handlers_installed = True

    for sig_name in ("SIGINT", "SIGTERM"):
        sig = getattr(signal, sig_name, None)
        if sig is None:
            continue
        with contextlib.suppress(ValueError, OSError):
            signal.signal(sig, _handle_signal)

    atexit.register(finalize_shutdown)


def exit_process(exit_code: int = 0) -> None:
    """Finalize shutdown and terminate the process."""
    finalize_shutdown()
    clear_app()
    sys.exit(exit_code)
