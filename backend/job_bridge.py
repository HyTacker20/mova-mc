"""Thread-safe bridge from ProgressReporter to asyncio queues for SSE streaming.

Pipeline stages run inside asyncio.to_thread(), so ProgressReporter.report()
is called from OS threads — not the event loop thread.  We use
loop.call_soon_threadsafe() to safely enqueue events, then each SSE endpoint
drains its own per-client queue.
"""

from __future__ import annotations

import asyncio
import threading
from typing import Any


class SseBridge:
    """Fan-out bridge: one ProgressReporter subscriber → N per-client queues.

    Create one SseBridge per TranslationJob before subscribing the reporter.
    Each SSE client calls subscribe() to get its own queue; unsubscribe() when
    the connection closes.
    """

    def __init__(self, loop: asyncio.AbstractEventLoop) -> None:
        self._loop = loop
        self._queues: set[asyncio.Queue[dict[str, Any] | None]] = set()
        self._lock = threading.Lock()

    def subscribe(self) -> asyncio.Queue[dict[str, Any] | None]:
        """Create and register a per-client queue. Called on the event-loop thread."""
        q: asyncio.Queue[dict[str, Any] | None] = asyncio.Queue()
        with self._lock:
            self._queues.add(q)
        return q

    def unsubscribe(self, q: asyncio.Queue[dict[str, Any] | None]) -> None:
        """Remove a client queue. Called on the event-loop thread."""
        with self._lock:
            self._queues.discard(q)

    def on_event(self, event: str, **data: Any) -> None:
        """Called from any thread — dispatches the event to all client queues."""
        frame: dict[str, Any] = {"event": event, "data": data}

        def _put() -> None:
            with self._lock:
                queues = list(self._queues)
            for q in queues:
                q.put_nowait(frame)

        self._loop.call_soon_threadsafe(_put)

    def close(self) -> None:
        """Send the sentinel (None) to all client queues to close SSE streams."""

        def _close() -> None:
            with self._lock:
                queues = list(self._queues)
            for q in queues:
                q.put_nowait(None)

        self._loop.call_soon_threadsafe(_close)
