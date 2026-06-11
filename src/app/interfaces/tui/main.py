"""
Entry point for the Textual-based interactive TUI.
Preserves public signature: def main(debug: bool = False) -> None
"""

from __future__ import annotations

from loguru import logger

from ...logging_config import setup_logging_for_tui
from ...utils.shutdown import exit_process, install_signal_handlers, register_app
from .app import TranslationApp


def main(debug: bool = False) -> None:
    """Launch the Textual TUI application.

    Args:
        debug: Enable debug-level logging output.
    """
    exit_code = 0
    install_signal_handlers()
    try:
        # TUI mode: file-only logging so no loguru/tracebacks reach stderr
        setup_logging_for_tui()
        logger.info("Starting MovaMC TUI (debug={})", debug)

        app = TranslationApp(debug=debug)
        register_app(app)
        app.run()
    except KeyboardInterrupt:
        exit_code = 0
    finally:
        exit_process(exit_code)
