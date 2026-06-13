"""Thread-safe bridge from ProgressReporter to asyncio queues for SSE streaming.

Progress events may originate from worker threads (``asyncio.to_thread`` stages)
or from the event loop itself (async translate stage).  Worker-thread events
use ``loop.call_soon_threadsafe()``; same-loop events are enqueued immediately
so fast batch translation cannot finish before SSE clients receive frames.
"""

from __future__ import annotations

import asyncio
import threading
from collections import deque
from typing import Any

_MAX_HISTORY = 2_000


class SseBridge:
    """Fan-out bridge: one ProgressReporter subscriber → N per-client queues.

    Create one SseBridge per TranslationJob before subscribing the reporter.
    Each SSE client calls subscribe() to get its own queue; unsubscribe() when
    the connection closes.  A ring buffer replays recent events to subscribers
    that connect after the job has already emitted progress (common with batch).
    """

    def __init__(self, loop: asyncio.AbstractEventLoop) -> None:
        self._loop = loop
        self._queues: set[asyncio.Queue[dict[str, Any] | None]] = set()
        self._lock = threading.Lock()
        self._history: deque[dict[str, Any]] = deque(maxlen=_MAX_HISTORY)

    def subscribe(self) -> asyncio.Queue[dict[str, Any] | None]:
        """Create and register a per-client queue. Called on the event-loop thread."""
        q: asyncio.Queue[dict[str, Any] | None] = asyncio.Queue()
        with self._lock:
            self._queues.add(q)
            history = list(self._history)
        for frame in history:
            q.put_nowait(frame)
        return q

    def unsubscribe(self, q: asyncio.Queue[dict[str, Any] | None]) -> None:
        """Remove a client queue. Called on the event-loop thread."""
        with self._lock:
            self._queues.discard(q)

    def _dispatch(self, frame: dict[str, Any]) -> None:
        with self._lock:
            self._history.append(frame)
            queues = list(self._queues)
        for q in queues:
            q.put_nowait(frame)

    def _run_on_loop(self, fn: Any) -> None:
        """Run *fn* immediately on the loop thread, or schedule thread-safely."""
        try:
            running = asyncio.get_running_loop()
        except RuntimeError:
            running = None
        if running is self._loop:
            fn()
        else:
            self._loop.call_soon_threadsafe(fn)

    def on_event(self, event: str, **data: Any) -> None:
        """Called from any thread — dispatches the event to all client queues."""
        frame: dict[str, Any] = {"event": event, "data": data}
        self._run_on_loop(lambda: self._dispatch(frame))

    def close(self) -> None:
        """Send the sentinel (None) to all client queues to close SSE streams."""

        def _close() -> None:
            with self._lock:
                queues = list(self._queues)
            for q in queues:
                q.put_nowait(None)

        self._run_on_loop(_close)
