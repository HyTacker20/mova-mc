from __future__ import annotations

import signal
from unittest.mock import MagicMock, patch

from app.utils.shutdown import (
    clear_app,
    finalize_shutdown,
    install_signal_handlers,
    register_app,
    request_shutdown,
)


class TestShutdown:
    def setup_method(self) -> None:
        clear_app()

    def teardown_method(self) -> None:
        clear_app()

    def test_request_shutdown_cancels_workers_and_exits(self) -> None:
        app = MagicMock()
        app._exit = False
        register_app(app)

        request_shutdown(0)

        app.workers.cancel_all.assert_called_once()
        app.exit.assert_called_once_with(return_code=0)

    def test_finalize_shutdown_without_app(self) -> None:
        finalize_shutdown()  # should not raise

    def test_signal_handler_first_interrupt_requests_shutdown(self) -> None:
        app = MagicMock()
        app._exit = False
        register_app(app)

        with patch("app.utils.shutdown._handlers_installed", False):
            install_signal_handlers()

        with patch("app.utils.shutdown.request_shutdown") as mock_request:
            signal.getsignal(signal.SIGINT)(signal.SIGINT, None)
            mock_request.assert_called_once_with(0)

    def test_clear_app_resets_state(self) -> None:
        register_app(MagicMock())
        clear_app()
        request_shutdown(0)
        # No app registered — exit should be a no-op
