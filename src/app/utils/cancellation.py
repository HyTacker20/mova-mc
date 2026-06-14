"""Cancellation token for cooperative pipeline cancellation.

Uses a ``threading.Event`` as a global flag.  Pipeline stages check
``raise_if_set()`` at safe points (between mods, files, chunks) so that
Ctrl+C is responsive even when threads are blocked on I/O.

Usage::

    from ...utils.cancellation import cancel_token

    # In a long-running loop:
    cancel_token.raise_if_set()

    # From Ctrl+C handler:
    cancel_token.set()

    # Before starting the pipeline:
    cancel_token.clear()
"""

from __future__ import annotations

import asyncio
import threading
from typing import ClassVar


class _CancellationToken:
    """Singleton cancellation token backed by ``threading.Event``.

    Thread-safe — ``set()`` and ``raise_if_set()`` can be called from any
    thread.  The token is cleared before each pipeline run.
    """

    _event: ClassVar[threading.Event] = threading.Event()

    @classmethod
    def set(cls) -> None:
        cls._event.set()

    @classmethod
    def clear(cls) -> None:
        cls._event.clear()

    @classmethod
    def is_set(cls) -> bool:
        return cls._event.is_set()

    @classmethod
    def raise_if_set(cls) -> None:
        """Raise ``CancelledError`` if cancellation was requested.

        Safe to call inside ``except`` blocks (does not mask existing
        exceptions).  Use at safe checkpoints in long-running loops.

        Uses ``asyncio.CancelledError`` rather than ``KeyboardInterrupt``
        because ``KeyboardInterrupt`` in an async context causes the event
        loop to cancel *all* tasks, which produces cascading
        ``CancelledError`` noise in the lifespan and HTTP handlers.
        """
        if cls._event.is_set():
            raise asyncio.CancelledError()


cancel_token = _CancellationToken()
